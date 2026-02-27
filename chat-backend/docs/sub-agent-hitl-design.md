# 서브에이전트 Human-in-the-Loop (HITL) 설계

## 목표

FabTraceAgent 등 서브에이전트가 내부 도구를 호출할 때, 각 단계별로 사용자에게 "이 도구를 실행해도 될까요?" 확인을 받는 HITL 흐름 구현.

## 현재 구조

```
메인 에이전트 (HITL + Checkpointer)
  └── tools 노드: analyze_fab_trace 호출
        └── FabTraceAgent.ainvoke() → 8개 도구를 한번에 실행 (중간 확인 없음)
```

- 메인 에이전트 레벨에서만 HITL 존재 (analyze_fab_trace 호출 전 확인)
- 서브에이전트 내부 도구 호출에는 HITL 없음

## 선택한 방식: 빌트인 HumanInTheLoopMiddleware + Checkpointer

### 핵심 아이디어

`as_tool()` 안에서 interrupt/resume 루프를 처리. 메인 에이전트는 관여하지 않음.

```
메인 에이전트 tools 노드
  └── analyze_fab_trace() ← as_tool() 함수 (async)
        │
        ├── agent.ainvoke() → result에 __interrupt__ 포함
        ├── while "__interrupt__" in result:
        │     ├── interrupt에서 tool_name, tool_args 추출
        │     ├── SSE로 sub_confirm 전송 (progress queue 경유)
        │     ├── asyncio.Event.wait() ← 사용자 응답 대기
        │     ├── 승인/거부 결정
        │     └── agent.ainvoke(Command(resume=...), config) → 재개
        ├── 최종 응답 캡처
        └── return "최종 분석 결과..."
```

메인 에이전트 입장에서는 `as_tool()`이 그냥 좀 오래 걸리는 async 함수일 뿐.

### as_tool() 구현 스케치

```python
from uuid import uuid4
from langgraph.types import Command

async def analyze_fab_trace(request: str) -> str:
    sub_thread_id = str(uuid4())
    config = {"configurable": {"thread_id": sub_thread_id}}

    # 첫 실행
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=request)]},
        config=config,
    )

    # interrupt가 있으면 반복
    while "__interrupt__" in result:
        interrupt = result["__interrupt__"][0]
        action = interrupt.value["action_requests"][0]
        tool_name = action["name"]
        tool_args = action["arguments"]

        # SSE로 confirm 전송 + 사용자 응답 대기
        approved = await wait_for_user_approval(tool_name, tool_args)

        # resume
        decision = {"type": "approve"} if approved else {"type": "reject"}
        result = await agent.ainvoke(
            Command(resume={"decisions": [decision]}),
            config=config,
        )

    return self.extract_ai_content(result)
```

### 사용자 응답 브릿지: asyncio.Event 패턴

두 개의 독립적인 HTTP 요청을 같은 프로세스 내 메모리로 연결.

```
[요청 1: 채팅 메시지 (SSE 스트림)]       [요청 2: 승인/거부 (POST)]
     │                                        │
     ├── Event 생성                           │
     ├── _pending_confirms[confirm_id]        │
     │     = (event, response_holder)         │
     ├── SSE로 confirm_id 전송 → 프론트       │
     ├── await event.wait() ← 대기            │
     │         ┌──────────────────────────────┘
     │         │  _pending_confirms에서 찾기
     │         │  response_holder["approved"] = True
     │         │  event.set() ← 대기 해제
     │         ▼
     ├── response_holder 확인
     └── 승인이면 resume / 거부면 reject
```

#### 모듈 레벨 레지스트리

```python
# progress.py
_pending_confirms: dict[str, tuple[asyncio.Event, dict]] = {}

def register_confirm(confirm_id: str) -> tuple[asyncio.Event, dict]:
    event = asyncio.Event()
    response_holder = {"approved": None}
    _pending_confirms[confirm_id] = (event, response_holder)
    return event, response_holder

def resolve_confirm(confirm_id: str, approved: bool):
    entry = _pending_confirms.pop(confirm_id, None)
    if entry:
        event, response_holder = entry
        response_holder["approved"] = approved
        event.set()
```

#### 새 API 엔드포인트

```python
@router.post("/chat/sub-confirm")
async def sub_confirm(confirm_id: str, approved: bool):
    resolve_confirm(confirm_id, approved)
    return {"status": "ok"}
```

### 다중 라운드 HITL 흐름

SSE 스트림(요청 1)은 서브에이전트가 완료될 때까지 열려있으므로, 여러 번의 interrupt/resume이 가능.

```
요청 1 (SSE) ─────── 시간 ──────────────────────────────→
│
├─ Tool 1 → Event1 → SSE confirm → await event1.wait()
│   요청 2 (POST) → event1.set() ─────────────────────┘
├─ Tool 1 실행 → 완료
├─ Tool 2 → Event2 → SSE confirm → await event2.wait()
│   요청 3 (POST) → event2.set() ─────────────────────┘
├─ Tool 2 실행 → 완료
├─ ...반복...
└─ 최종 응답 → SSE DONE
```

- 매 도구 호출마다 새 `asyncio.Event` + 새 `confirm_id` 생성
- `await event.wait()`는 non-blocking (이벤트 루프 차단 안함)
- 요청 2, 3, 4가 들어와도 정상 처리

### 필요한 변경 사항

| 파일 | 변경 내용 |
|------|-----------|
| `ai/agents/base.py` | `get_checkpointer()` 오버라이드 가능하도록 (이미 있음) |
| `ai/agents/fab_trace_agent.py` | HITL 미들웨어 추가, as_tool() interrupt 루프 구현 |
| `ai/graph/progress.py` | `_pending_confirms` 레지스트리 + `emit_sub_confirm()` 추가 |
| `ai/graph/orchestrator.py` | `sub_confirm` 이벤트 타입 SSE 처리 |
| `ai/graph/schema/stream.py` | `SUB_CONFIRM` StreamStatus 추가 |
| `router/chat_router.py` | `POST /chat/sub-confirm` 엔드포인트 추가 |
| 프론트엔드 | `sub_confirm` SSE 처리 + 승인/거부 UI + POST 호출 |

### 방식 비교 (참고)

|  | 빌트인 HITL + Checkpointer | Custom 미들웨어 + Event |
|--|---------------------------|------------------------|
| checkpointer | 필요 (InMemorySaver) | 불필요 |
| thread_id | 서브에이전트별 필요 | 불필요 |
| as_tool() | ainvoke 루프 + interrupt 감지 + resume | 변경 없음 |
| 미들웨어 | 빌트인 HumanInTheLoopMiddleware | Custom awrap_tool_call |
| 사용자 응답 브릿지 | asyncio.Event (동일) | asyncio.Event (동일) |
| LangChain 패턴 | 공식 패턴 | 커스텀 |

**선택: 빌트인 HITL + Checkpointer** (공식 패턴, 유지보수 안전)

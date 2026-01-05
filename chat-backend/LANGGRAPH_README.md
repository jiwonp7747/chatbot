# LangGraph 기반 채팅 시스템

## 개요

기존 모놀리식 채팅 처리 로직을 LangGraph를 사용하여 4개의 독립적인 노드로 분리하여 확장성과 유지보수성을 향상시켰습니다.

## 아키텍처

### 노드 구성

```
START
  ↓
[1. load_history] - 대화 기록 로드
  ↓
[2. analyze_intent] - 의도 분석 + 필요 도구 파악
  ↓
[3. call_tools] - MCP 도구 호출
  ↓
[4. generate_response] - 메시지 구성 + 추가 도구 필요 여부 판단
  ↓
[5. should_continue?] - 조건부 라우팅
  ↓ (needs_more_tools)
  └─→ call_tools (반복 루프, 최대 5회)
  ↓ (done)
[6. stream_response] - 응답 스트리밍
  ↓
END
```

### 파일 구조

```
service/
├── chat_langgraph_service.py  # LangGraph 메인 로직
└── nodes/
    ├── __init__.py
    ├── load_history.py         # 노드 1: 대화 기록 로드
    ├── analyze_intent.py       # 노드 2: 의도 분석 + 도구 파악
    ├── call_tools.py           # 노드 3: MCP 도구 호출 (NEW)
    ├── generate_response.py    # 노드 4: 응답 생성 + 추가 도구 판단
    └── stream_response.py      # 노드 5: 응답 스트리밍

schema/
└── chat_graph_schema.py        # LangGraph State 정의 (확장됨)
```

## API 엔드포인트

### 신규: `/chat/stream-chat-graph` (LangGraph 기반)

**요청:**
```bash
POST /chat/stream-chat-graph
Content-Type: application/json

{
  "chat_session_id": 1,
  "prompt": "안녕하세요",
  "model": "gpt-5.1-mini"
}
```

**응답:** SSE (Server-Sent Events) 스트리밍
```
data: {"content":"안녕","status":"streaming","error":null}

data: {"content":"하세요","status":"streaming","error":null}

data: {"content":"","status":"done","error":null}
```

### 레거시: `/chat/stream-chat` (기존 방식)

기존 모놀리식 구조로 동작하는 엔드포인트입니다. 호환성을 위해 유지됩니다.

## 주요 기능

### 1. 대화 기록 로드 (load_history)

- DB에서 최근 10개의 메시지 조회
- 채팅 세션별로 대화 컨텍스트 유지
- 새 세션인 경우 빈 기록 반환

**구현 위치:** `service/nodes/load_history.py`

### 2. 의도 분석 + 도구 파악 (analyze_intent)

- **AI 기반 의도 분석**: LLM을 사용하여 사용자 의도 파악
- **필요 도구 식별**: 사용자 요청에 필요한 MCP 도구 자동 파악
- **구조화된 출력**: JSON 형식으로 의도 및 도구 정보 반환

**지원 의도 타입:**
- `general_chat`: 일반 대화
- `translation`: 번역 요청
- `code_generation`: 코드 작성 요청
- `question`: 질문
- `data_visualization`: 데이터 시각화 (차트 생성 등)
- `calculation`: 계산

**도구 예시:**
- `generate_yield_chart`: 수율 차트 생성
- `search_web`: 웹 검색
- `calculate`: 계산

**구현 위치:** `service/nodes/analyze_intent.py`

### 3. MCP 도구 호출 (call_tools) ⭐ NEW

- **MCP 서버 연결**: SSE 클라이언트를 통해 MCP 서버에 연결
- **도구 실행**: 분석된 도구 목록을 순차적으로 실행
- **결과 수집**: 각 도구의 실행 결과를 파싱하여 저장
- **에러 처리**: 도구 실행 실패 시 에러 정보 기록

**지원 결과 타입:**
- `text`: 텍스트 결과
- `image`: 이미지 데이터 (Base64)
- `resource`: 리소스 URI

**환경 변수:**
- `MCP_SERVER_SSE_URL`: MCP 서버 URL (기본값: `http://localhost:3000/sse`)

**구현 위치:** `service/nodes/call_tools.py`

### 4. 응답 생성 + 추가 도구 판단 (generate_response)

- **메시지 구성**: 시스템 프롬프트 + 대화 기록 + 도구 결과 + 사용자 입력 조합
- **도구 결과 포함**: 실행된 도구의 결과를 컨텍스트에 포함
- **추가 도구 필요 여부 판단**: AI가 추가 도구 호출이 필요한지 자동 판단
- **반복 제어**: 최대 5회까지 도구 호출 반복 가능

**구현 위치:** `service/nodes/generate_response.py`

### 5. 조건부 라우팅 (should_continue)

- **반복 루프 제어**: `needs_more_tools` 플래그에 따라 도구 호출 반복
- **무한 루프 방지**: 최대 5회 반복 제한
- **자동 종료**: 조건 충족 시 스트리밍 단계로 이동

**구현 위치:** `service/chat_langgraph_service.py:87`

### 6. 응답 스트리밍 (stream_response)

- OpenAI API 스트리밍 호출
- SSE 형식으로 실시간 응답 전송
- 연결 끊김 감지 및 처리
- DB 저장 (Middleware를 통한 콜백)

**구현 위치:** `service/nodes/stream_response.py`

## State 관리

### ChatGraphState

```python
{
    # 입력
    "chat_session_id": int,
    "user_prompt": str,
    "model": str,

    # 노드 1 출력
    "message_history": List[Dict],

    # 노드 2 출력
    "intent_analysis": Dict,
    "tools_to_call": List[Dict],  # 호출할 도구 목록

    # 노드 3 출력
    "tool_results": List[Dict],  # 도구 실행 결과

    # 노드 4 출력
    "messages": List[Dict],
    "needs_more_tools": bool,  # 추가 도구 필요 여부
    "iteration_count": int,  # 반복 횟수

    # 노드 5 출력
    "ai_response": str,

    # 메타데이터
    "user_chat_created_at": datetime,
    "stream_id": str,
    "error": Optional[str]
}
```

### State 필드 상세 설명

**tools_to_call**:
```python
[
    {
        "name": "generate_yield_chart",
        "arguments": {
            "type": "PIPE",
            "data": [...]
        },
        "reason": "수율 차트 생성이 필요"
    }
]
```

**tool_results**:
```python
[
    {
        "tool": "generate_yield_chart",
        "success": True,
        "error": None,
        "result": {
            "content": [
                {
                    "type": "image",
                    "data": "base64_encoded_image",
                    "mimeType": "image/png"
                }
            ],
            "metadata": {}
        }
    }
]
```

## 확장 가능성

### 1. 의도 분석 고도화

```python
# 현재: 규칙 기반
if "번역" in user_prompt:
    intent = "translation"

# 향후: LLM 기반
intent = await analyze_with_llm(user_prompt, message_history)
```

### 2. 조건부 라우팅

```python
# 의도에 따라 다른 응답 생성 전략 선택
if intent == "code_generation":
    workflow.add_edge("analyze_intent", "code_generation_node")
else:
    workflow.add_edge("analyze_intent", "generate_response")
```

### 3. 멀티 모델 지원

```python
# 의도에 따라 다른 모델 사용
if intent == "translation":
    model = "gpt-5.1-nano"  # 빠르고 저렴한 모델
elif intent == "code_generation":
    model = "gpt-5.1"  # 더 강력한 모델
```

### 4. 캐싱 및 최적화

```python
# 유사한 질문에 대한 캐싱
cached_response = await check_cache(user_prompt)
if cached_response:
    return cached_response
```

### 5. 병렬 처리

```python
# 여러 노드를 병렬로 실행
workflow.add_conditional_edges(
    "load_history",
    lambda x: ["analyze_intent", "load_context"],
    {
        "analyze_intent": analyze_intent_node,
        "load_context": load_context_node
    }
)
```

## 테스트

### 1. 서버 실행

```bash
# 환경 변수 설정
export OPENAI_API_KEY="your-api-key"

# 서버 시작
python main.py
```

### 2. cURL 테스트

```bash
curl -X POST http://localhost:8000/chat/stream-chat-graph \
  -H "Content-Type: application/json" \
  -d '{
    "chat_session_id": 1,
    "prompt": "안녕하세요",
    "model": "gpt-5.1-mini"
  }'
```

### 3. Python 테스트 스크립트

```python
import httpx

async def test_chat():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/chat/stream-chat-graph",
            json={
                "chat_session_id": 1,
                "prompt": "안녕하세요",
                "model": "gpt-5.1-mini"
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    print(line[6:])  # "data: " 제거

# 실행
import asyncio
asyncio.run(test_chat())
```

## 마이그레이션 가이드

### 기존 코드에서 LangGraph로 전환

**Before (기존):**
```python
@router.post("/stream-chat")
async def stream_chat(chat_request: ChatRequest, ...):
    return StreamingResponse(
        process_chat_request(chat_request, db, http_request),
        media_type="text/event-stream"
    )
```

**After (LangGraph):**
```python
@router.post("/stream-chat-graph")
async def stream_chat_graph(chat_request: ChatRequest, ...):
    return StreamingResponse(
        process_chat_with_langgraph(chat_request, db, http_request),
        media_type="text/event-stream"
    )
```

### 클라이언트 코드 변경

단순히 엔드포인트 URL만 변경하면 됩니다:

```javascript
// Before
const response = await fetch('/chat/stream-chat', {...})

// After
const response = await fetch('/chat/stream-chat-graph', {...})
```

## 장점

### 1. 확장성
- 각 노드를 독립적으로 수정/확장 가능
- 새로운 노드 추가가 용이

### 2. 유지보수성
- 각 노드의 책임이 명확히 분리
- 테스트가 용이

### 3. 가독성
- 전체 흐름을 한눈에 파악 가능
- 각 단계의 역할이 명확

### 4. 재사용성
- 노드를 다른 워크플로우에서 재사용 가능
- 조합을 통한 다양한 시나리오 구현

## 향후 계획

1. **의도 분석 고도화**: LLM 기반 의도 분석
2. **멀티 모달 지원**: 이미지, 음성 입력 처리
3. **RAG 통합**: 외부 지식 베이스 연동
4. **A/B 테스트**: 다양한 전략 비교
5. **모니터링**: 각 노드별 성능 메트릭 수집

## 참고

- [LangGraph 공식 문서](https://python.langchain.com/docs/langgraph)
- [LangChain 가이드](https://python.langchain.com/docs/get_started/introduction)

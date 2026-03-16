"""
오케스트레이터 - Deep Agent 패턴

create_deep_agent의 네이티브 subagents를 사용합니다.
서브에이전트는 agents/ 패키지에서 SubAgent 딕셔너리로 정의됩니다.

흐름:
  사용자 요청 → 메인 에이전트 → task() 도구로 서브에이전트 위임 → 결과 반환 → 최종 응답
  (HITL 활성화 시: 서브에이전트 내 도구 호출 전 interrupt → 사용자 확인 → resume)

구조:
  메인 에이전트 (라우팅 + 응답 생성)
    ├── search-documents   → RAG 서브에이전트 (tag_search, semantic_search)
    ├── execute-tools      → Tool 서브에이전트 (MCP 도구들)
    ├── analyze-fab-trace  → Fab Trace 서브에이전트 (설비 분석)
    └── 직접 응답 (도구 불필요시)
"""
import json
import logging
import time
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage

from opentelemetry import trace as otel_trace
from opentelemetry.trace import StatusCode

from ai.agents.rag_agent import create_rag_subagent
from ai.agents.tool_agent import create_tool_subagent
from ai.agents.fab_trace_agent import create_fab_trace_subagent
from ai.backend import get_database_backend
from ai.checkpointer import get_checkpointer
from ai.middleware.large_data_middleware import create_large_data_middleware
from ai.graph.schema.graph_state import ChatGraphState
from ai.graph.schema.context import ChatContext
from ai.graph.schema.stream import AvailableTool, ChatResponse, HitlToolCall, StreamStatus, StreamResult
from ai.middleware.tool_call_inject_middleware import create_tool_call_inject_middleware
from ai.middleware.tool_call_review_middleware import create_tool_call_review_middleware
from ai.tools.mcp.wrapper import wrap_mcp_tools
from mcp_hub import get_mcp_registry
from util.sse_formatter import SSEFormatter

logger = logging.getLogger("chat-server")

# 모델별 에이전트 캐시 (매 요청마다 재빌드 방지) — (agent, created_at) 튜플
_agent_cache: dict[str, tuple[object, float]] = {}
_CACHE_TTL = 3600  # 1시간


def invalidate_agent_cache(model_string: str | None = None):
    """에이전트 캐시 무효화. model_string이 None이면 전체 초기화."""
    if model_string:
        _agent_cache.pop(model_string, None)
    else:
        _agent_cache.clear()
    logger.info(f"🔄 에이전트 캐시 무효화: {model_string or '전체'}")


# HITL interrupt 시 도구 정보 보관 (thread_id → {"tools": [...], "count": N, ...})
_interrupted_tools: dict[str, dict] = {}

# 서브에이전트별 사용 가능한 도구 목록 (agent_name → [tool_name, ...])
_available_tools_registry: dict[str, list[str]] = {}

# 도구별 JSON Schema 레지스트리 (tool_name → {name, description, schema, agent})
_tool_schema_registry: dict[str, dict] = {}


import re

def _enrich_schema_descriptions(schema: dict, docstring: str) -> None:
    """docstring의 Args 섹션을 파싱하여 schema properties에 description을 주입한다."""
    if not docstring or "properties" not in schema:
        return
    # Args: 섹션 추출
    args_match = re.search(r"Args:\s*\n((?:\s+\w+:.*(?:\n|$))+)", docstring)
    if not args_match:
        return
    args_block = args_match.group(1)
    # "    param_name: 설명 텍스트" 패턴 파싱
    for match in re.finditer(r"^\s+(\w+):\s*(.+)$", args_block, re.MULTILINE):
        param_name = match.group(1)
        param_desc = match.group(2).strip()
        if param_name in schema["properties"]:
            schema["properties"][param_name]["description"] = param_desc
    # 스키마 최상위의 중복 description 제거 (docstring 전체 → 프론트에서 불필요)
    schema.pop("description", None)


def get_tool_schemas(tool_names: list[str] | None = None) -> list[dict]:
    """도구 스키마 조회. tool_names가 None이면 전체 반환."""
    if tool_names is None:
        return list(_tool_schema_registry.values())
    return [_tool_schema_registry[n] for n in tool_names if n in _tool_schema_registry]

MAIN_AGENT_PROMPT = """당신은 AI 어시스턴트 오케스트레이터입니다.
사용자의 요청을 분석하여 적절한 전문가에게 task 도구로 위임하세요.

## 작업절차 

바로 답변할 수 있는 단순한 질문이외 복잡한 작업 (팹 관리)의 경우 write_todos 도구를 사용하세요.

## 위임 규칙 (반드시 준수)

아래 키워드가 포함된 요청은 **절대 직접 답변하지 말고** 반드시 해당 서브에이전트에 task 도구로 위임하세요:

| 키워드 | 서브에이전트 |
|--------|-------------|
| 팹, 설비, 불량, 수율, 트레이스, LOT, 웨이퍼, 파라미터, FDC, 알람, OOS, 장비, 설비 건강도, 이력, 추적 | analyze-fab-trace |
| 문서, 검색, 자료, 찾아, 알려줘, 매뉴얼, 가이드, 규정, 절차 | search-documents |
| 차트, 그래프, 시각화, 메모리 | execute-tools |

## 직접 답변 허용 조건

다음 조건을 **모두** 만족할 때만 직접 답변하세요:
- 위 키워드에 해당하지 않는 순수한 일반 대화 (인사, 번역, 코드 작성 등)
- 도구 호출 없이도 정확한 답변이 가능한 경우

**확신이 없으면 도구를 호출하세요. "분석 중입니다", "확인해보겠습니다" 같은 빈 약속만 하고 끝내는 것은 절대 금지입니다.**

## 기타 규칙
- 한 턴에 task 도구를 최대 3번까지만 호출하세요.
- 도구 결과가 부족하더라도 이미 받은 결과를 바탕으로 최선의 답변을 제공하세요.
- 전문가의 결과를 바탕으로 사용자에게 자연스러운 최종 답변을 제공하세요.
"""


def _content_to_str(content) -> str:
    """content가 list일 경우 텍스트만 추출하여 str로 변환"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content) if content else ""


def _extract_agent_name(namespace: tuple) -> str:
    """subgraphs=True의 namespace 튜플에서 서브에이전트 이름 추출

    namespace 예: ('search-documents:abc123',) → 'search-documents'
    """
    if namespace:
        first = namespace[0]
        return first.split(":")[0] if ":" in first else first
    return "main"


def _parse_description(raw: str) -> tuple[str, dict | None]:
    """description 문자열에서 reason과 tool_detail을 분리한다.

    JSON 형식이면 파싱, 아니면 전체를 tool_detail로 사용.
    """
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            detail = parsed.get("tool_detail")
            if isinstance(detail, str):
                detail = {"description": detail}
            return parsed.get("reason", ""), detail
    except (json.JSONDecodeError, TypeError):
        pass
    return "", {"description": raw} if raw else None


def _build_interrupt_context(
    action_requests: list[dict], fallback_reasoning: str,
) -> tuple[str | None, list[HitlToolCall]]:
    """interrupt action_requests에서 공통 reasoning과 도구별 HitlToolCall 목록을 생성한다.

    Returns:
        (tool_context, tool_calls) 튜플
        - tool_context: 에이전트 추론 근거 (1회, 공통)
        - tool_calls: 개별 도구 호출 정보 리스트
    """
    reason = ""
    hitl_tool_calls: list[HitlToolCall] = []

    for action in action_requests:
        tool_name = action.get("name", "unknown")
        tool_args = action.get("args") or action.get("arguments", {})

        description = action.get("description")
        if description:
            parsed_reason, tool_detail = _parse_description(str(description))
            if not reason and parsed_reason:
                reason = parsed_reason
        else:
            tool_detail = None

        hitl_tool_calls.append(HitlToolCall(
            name=tool_name,
            args=tool_args,
            detail=tool_detail,
        ))

    if not reason:
        reason = fallback_reasoning

    return (reason or None), hitl_tool_calls


def _extract_interrupt_action_requests(chunk: dict) -> list[dict] | None:
    """chunk에서 interrupt action_requests를 추출한다."""
    if "__interrupt__" not in chunk:
        return None
    interrupt = chunk["__interrupt__"][0]
    return interrupt.value.get("action_requests", [])



def _collect_subagent_updates(
    chunk: dict,
    agent_name: str,
    last_reasoning: str,
) -> tuple[list[str], str]:
    """서브에이전트 chunk를 SSE 메시지 목록으로 변환한다."""
    sse_messages: list[str] = []
    updated_reasoning = last_reasoning

    for key, value in chunk.items():
        # agent 노드가 완료되었을 때
        if key == "agent":
            logger.info(f"***** 서브 에이전트 도구 호출 reasoning : {value} *****")
            msgs = value.get("messages", [])
            for msg in msgs:
                content = _content_to_str(msg.content) if hasattr(msg, "content") and msg.content else ""

                if content:
                    updated_reasoning = content
                    sub_resp = ChatResponse(
                        content=content,
                        status=StreamStatus.SUB_PROGRESS,
                        agent_name=agent_name,
                    )
                    sse_messages.append(SSEFormatter.format(sub_resp))

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_names = [tc["name"] for tc in msg.tool_calls]
                    sub_resp = ChatResponse(
                        content=f"🔧 {', '.join(tool_names)} 호출 중...",
                        status=StreamStatus.SUB_PROGRESS,
                        agent_name=agent_name,
                        sub_tools=tool_names,
                        parallel=len(tool_names) > 1,
                    )
                    sse_messages.append(SSEFormatter.format(sub_resp))

        # 도구 노드가 완료되었을 때
        elif key == "tools":
            msgs = value.get("messages", [])
            for msg in msgs:
                if hasattr(msg, "name"):
                    artifact = getattr(msg, "artifact", None)
                    sub_resp = ChatResponse(
                        content=f"✅ {msg.name} 완료",
                        status=StreamStatus.SUB_PROGRESS,
                        agent_name=agent_name,
                        sub_tools=[msg.name],
                        parallel=False,
                        artifact=artifact if isinstance(artifact, dict) else None,
                    )
                    sse_messages.append(SSEFormatter.format(sub_resp))

    return sse_messages, updated_reasoning


def _collect_main_updates(chunk: dict, ai_response: str) -> tuple[list[str], str]:
    """메인 에이전트 chunk를 SSE 메시지 목록으로 변환한다."""
    sse_messages: list[str] = []
    updated_ai_response = ai_response

    for key, value in chunk.items():
        if key == "model":
            msgs = value.get("messages", [])
            for msg in msgs:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tc_name = tc.get("name", "unknown")
                        progress = ChatResponse(
                            content=f"⚡ {tc_name} 실행 중...",
                            status=StreamStatus.PROGRESS,
                        )
                        sse_messages.append(SSEFormatter.format(progress))

                if isinstance(msg, AIMessage) and msg.content:
                    updated_ai_response = _content_to_str(msg.content)

        elif key == "tools":
            msgs = value.get("messages", [])
            for msg in msgs:
                if hasattr(msg, "name"):
                    artifact = getattr(msg, "artifact", None)
                    if isinstance(artifact, dict) and artifact:
                        tool_done = ChatResponse(
                            content=f"✅ {msg.name} 완료",
                            status=StreamStatus.SUB_PROGRESS,
                            sub_tools=[msg.name],
                            parallel=False,
                            artifact=artifact,
                        )
                        sse_messages.append(SSEFormatter.format(tool_done))
                    logger.info(f"✅ 서브에이전트 완료: {msg.name}")

    return sse_messages, updated_ai_response


class Orchestrator:
    """Deep Agent 패턴 오케스트레이터

    서브에이전트는 agents/ 패키지에서 SubAgent 딕셔너리로 정의됩니다.
    create_deep_agent가 서브에이전트 빌드/래핑/결과추출을 모두 내장합니다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._mcp_tools: list | None = None

    async def _load_mcp_tools(self) -> list:
        """MCP 도구 로드 (lazy loading)"""
        if self._mcp_tools is not None:
            return self._mcp_tools

        try:
            self._mcp_tools = await wrap_mcp_tools()
            logger.info(f"🔧 MCP 도구 {len(self._mcp_tools)}개 로드")
        except Exception as e:
            logger.warning(f"⚠️ MCP 도구 로드 실패 (무시): {e}")
            self._mcp_tools = []

        return self._mcp_tools

    async def _get_or_build_agent(self, model_string: str, model_kwargs: dict | None = None):
        """에이전트 캐시에서 가져오거나 새로 빌드 (TTL 기반 만료)"""
        if model_string in _agent_cache:
            agent, created_at = _agent_cache[model_string]
            if time.time() - created_at < _CACHE_TTL:
                return agent
            logger.info(f"🔄 캐시 만료: {model_string}")

        agent = await self._build_main_agent(model_string, model_kwargs)
        _agent_cache[model_string] = (agent, time.time())
        return agent

    async def _build_main_agent(self, model_string: str, model_kwargs: dict | None = None):
        """서브에이전트를 구성하고 Deep Agent 생성"""
        mcp_tools = await self._load_mcp_tools()
        backend = get_database_backend()
        large_data_mw = create_large_data_middleware(backend)
        tool_call_review_mw = create_tool_call_review_middleware(model_string, 1)
        tool_call_inject_mw = create_tool_call_inject_middleware(model_string)

        subagents = [
            create_rag_subagent(),
            create_fab_trace_subagent(),
        ]
        if mcp_tools:
            # large_data_mw
            subagents.append(create_tool_subagent(mcp_tools, middleware=[large_data_mw]))

        # 서브에이전트별 도구 목록 및 스키마 레지스트리 등록
        for sa in subagents:
            sa_name = sa.get("name", "")
            if sa_name and "tools" in sa:
                tool_names = [t.name for t in sa["tools"]]
                _available_tools_registry[sa_name] = tool_names
                for t in sa["tools"]:
                    try:
                        if hasattr(t, "args_schema") and t.args_schema:
                            schema = t.args_schema.model_json_schema()
                        else:
                            schema = {}
                        # docstring Args 섹션에서 property별 description 주입
                        _enrich_schema_descriptions(schema, getattr(t, "description", ""))
                        _tool_schema_registry[t.name] = {
                            "name": t.name,
                            "description": getattr(t, "description", ""),
                            "schema": schema,
                            "agent": sa_name,
                        }
                    except Exception as e:
                        logger.warning(f"⚠️ 도구 스키마 추출 실패: {t.name}: {e}")

        # MCP 도구 스키마도 등록
        if mcp_tools:
            try:
                registry = get_mcp_registry()
                mcp_tool_list = await registry.list_all_tools()
                for mcp_tool in mcp_tool_list:
                    name = mcp_tool["name"]
                    _tool_schema_registry[name] = {
                        "name": name,
                        "description": mcp_tool.get("description", ""),
                        "schema": mcp_tool.get("inputSchema", {}),
                        "agent": "execute-tools",
                    }
            except Exception as e:
                logger.warning(f"⚠️ MCP 도구 스키마 등록 실패: {e}")

        logger.info(f"🤖 서브에이전트 {len(subagents)}개 구성 완료")

        # model_kwargs가 있으면 pre-build된 BaseChatModel 인스턴스 전달
        if model_kwargs:
            from langchain.chat_models import init_chat_model
            model = init_chat_model(model_string, **model_kwargs)
        else:
            model = model_string

        # checkpointer
        checkpointer = get_checkpointer()

        return create_deep_agent(
            model=model,
            subagents=subagents,
            checkpointer=checkpointer,
            middleware=[tool_call_inject_mw],
            system_prompt=MAIN_AGENT_PROMPT,
            backend=backend,
            context_schema=ChatContext,
        )

    @staticmethod
    def _build_messages(state: ChatGraphState) -> list:
        """state의 기존 messages에 현재 사용자 프롬프트를 추가"""
        messages = list(state.get("messages", []))

        user_prompt = state.get("user_prompt", "")
        rag_tags = state.get("rag_tags", [])

        if rag_tags:
            user_content = (
                f"{user_prompt}\n\n"
                f"[참고: 다음 태그로 문서 검색을 수행하세요: {', '.join(rag_tags)}]"
            )
        else:
            user_content = user_prompt

        messages.append(HumanMessage(content=user_content))
        return messages

    @staticmethod
    def _extract_response(result: dict) -> str:
        """에이전트 실행 결과에서 최종 AI 응답 추출"""
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return _content_to_str(msg.content)
        if messages and hasattr(messages[-1], "content"):
            return _content_to_str(messages[-1].content)
        return ""

    async def _run_agent_stream(
        self,
        agent,
        input_data,
        config: dict,
        context: ChatContext,
        thread_id: str,
        span,
        result: StreamResult,
    ) -> AsyncGenerator[str, None]:
        """agent.astream() 루프 — run() 내부에서 공통 호출

        Yields:
            flat SSE 문자열만 yield, 결과는 result 객체에 저장
        """
        ai_response = ""
        last_reasoning = ""       # HITL용 동적 추론 버퍼

        async for namespace, chunk in agent.astream(
            input_data,
            config=config,
            context=context,
            stream_mode="updates",
            subgraphs=True,
        ):
            # 1. interrupt 감지 (서브에이전트 내부에서 발생, 버블업됨)
            action_requests = _extract_interrupt_action_requests(chunk)
            if action_requests is not None:
                # TODO: deepagents의 create_deep_agent 구조에서 서브그래프 내부 interrupt가
                #  메인 레벨 PregelTask.interrupts에 노출되지 않음 (task.name="tools", interrupts=()).
                #  현재는 messages에서 마지막 AIMessage의 tool_calls → task → args.subagent_type으로
                #  우회 추출. LangGraph 또는 deepagents 업데이트 시 직접 식별 방식으로 개선 필요.
                interrupted_agent_name = ""
                try:
                    state_snapshot = await agent.aget_state(config)
                    for msg in reversed(state_snapshot.values.get("messages", [])):
                        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                            for tc in msg.tool_calls:
                                if tc.get("name") == "task":
                                    interrupted_agent_name = tc.get("args", {}).get("subagent_type", "")
                                    break
                            if interrupted_agent_name:
                                break
                except Exception as e:
                    logger.warning(f"⚠️ get_state로 interrupt 출처 식별 실패: {e}")

                tool_context, hitl_tool_calls = _build_interrupt_context(action_requests, last_reasoning)
                tool_names = [tc.name for tc in hitl_tool_calls]
                display_name = ", ".join(tool_names)
                available_names = _available_tools_registry.get(interrupted_agent_name, [])
                available = [
                    AvailableTool(
                        name=n,
                        description=_tool_schema_registry.get(n, {}).get("description", ""),
                    )
                    for n in available_names
                ]

                confirm = ChatResponse(
                    content=f"'{display_name}' 도구를 실행하시겠습니까?",
                    status=StreamStatus.CONFIRM,
                    thread_id=thread_id,
                    tool_calls=hitl_tool_calls,
                    tool_context=tool_context,
                    available_tools=available or None,
                    agent_name=interrupted_agent_name or None,
                )
                span.set_attribute("hitl.interrupted", True)
                span.set_attribute("hitl.tool_names", display_name)
                span.set_status(StatusCode.OK, "HITL interrupt")
                _interrupted_tools[thread_id] = {
                    "tools": tool_names,
                    "count": len(action_requests),
                    "original_tool_calls": [tc.model_dump() for tc in hitl_tool_calls],
                }
                result.is_confirm = True
                result.thread_id = thread_id
                yield SSEFormatter.format(confirm)
                logger.info(f"⏸️ HITL interrupt: agent={interrupted_agent_name}, tools={display_name}, count={len(action_requests)}, thread={thread_id}")
                return

            # 2. 서브에이전트 이벤트 (namespace가 비어있지 않음)
            if namespace:
                agent_name = _extract_agent_name(namespace)
                sse_messages, last_reasoning = _collect_subagent_updates(
                    chunk=chunk,
                    agent_name=agent_name,
                    last_reasoning=last_reasoning,
                )
                for sse_message in sse_messages:
                    yield sse_message
                continue

            # 3. 메인 에이전트 이벤트 (namespace가 빈 튜플)
            sse_messages, ai_response = _collect_main_updates(chunk=chunk, ai_response=ai_response)
            for sse_message in sse_messages:
                yield sse_message

        result.ai_response = ai_response

    async def run(
        self,
        thread_id: str,
        result: StreamResult,
        *,
        # runtime config (state가 아닌 configurable로 전달)
        token: str | None = None,
        # 모델 정보 (model_resolver에서 생성)
        model_string: str | None = None,
        model_kwargs: dict | None = None,
        # 신규 채팅용 (None이면 resume)
        initial_state: ChatGraphState | None = None,
        # Fork from checkpoint용
        checkpoint_id: str | None = None,
        # HITL resume용
        approved: bool | None = None,
        edit_message: str | None = None,
        edited_tool_calls: list | None = None,
    ) -> AsyncGenerator[str, None]:
        """통합 실행 메서드 — 신규 채팅과 HITL resume 모두 처리

        initial_state가 있으면 신규 채팅, None이면 HITL resume으로 동작합니다.
        """
        is_new_chat = initial_state is not None
        span_name = "orchestrator.run" if is_new_chat else "orchestrator.resume"
        tracer = otel_trace.get_tracer("chat-backend")

        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("thread.id", thread_id)

            if not is_new_chat:
                span.set_attribute("hitl.approved", approved)
                span.set_attribute("model", model_string)

            try:
                if is_new_chat:
                    # --- 신규 채팅 ---
                    state = initial_state

                    # 메인 에이전트 구성
                    span.set_attribute("model", model_string)
                    yield SSEFormatter.format(ChatResponse(
                        content="🔧 전문가 에이전트를 준비하고 있습니다...",
                        status=StreamStatus.PROGRESS,
                    ))

                    main_agent = await self._get_or_build_agent(model_string, model_kwargs)
                    logger.info(f"🤖 메인 에이전트 준비 완료: model={model_string}")

                    # 3. 메시지 구성
                    messages = self._build_messages(state)
                    yield SSEFormatter.format(ChatResponse(
                        content="🤖 생각 중입니다...",
                        status=StreamStatus.PROGRESS,
                    ))

                    input_data = {"messages": messages}

                    if checkpoint_id:
                        logger.info(f"🔀 Fork from checkpoint: {checkpoint_id}, thread={thread_id}")

                else:
                    # --- HITL resume ---
                    main_agent = await self._get_or_build_agent(model_string, model_kwargs)

                    # interrupt 시 저장해둔 도구 정보
                    interrupted_info = _interrupted_tools.pop(thread_id, None)
                    tool_count = interrupted_info["count"] if interrupted_info else 1

                    if edited_tool_calls:
                        # EDIT decision: 수정된 args로 도구 즉시 실행 (재추론 없음)
                        if len(edited_tool_calls) != tool_count:
                            logger.warning(f"⚠️ edited_tool_calls 수({len(edited_tool_calls)}) != tool_count({tool_count}), 보정")
                        resume_value = {"decisions": [
                            {"type": "edit", "edited_action": {"name": tc.name, "args": tc.args}}
                            for tc in edited_tool_calls
                        ]}
                        span.set_attribute("hitl.edit_decision", True)
                        logger.info(f"✏️ HITL EDIT decision: tools={[tc.name for tc in edited_tool_calls]}, thread={thread_id}")

                        yield SSEFormatter.format(ChatResponse(
                            content=f"✏️ 수정된 인자로 도구를 실행합니다...",
                            status=StreamStatus.PROGRESS,
                        ))

                    elif edit_message:
                        # MESSAGE MODIFICATION: 거부 사유 반영하여 다른 도구로 재시도
                        reject_msg = (
                            f"사용자가 도구 호출을 거부했습니다.\n"
                            f"사유: {edit_message}\n\n"
                            f"[필수 지침] 사용자의 거부 사유를 반영하여 반드시 다른 도구를 호출하거나, "
                            f"수정된 인자로 재시도하세요. 텍스트만 응답하고 종료하는 것은 금지입니다."
                        )
                        resume_value = {"decisions": [
                            {"type": "reject", "message": reject_msg} for _ in range(tool_count)
                        ]}
                        span.set_attribute("hitl.message_modification", True)
                        logger.info(f"💬 HITL 메시지 수정: message={edit_message}, thread={thread_id}")

                        yield SSEFormatter.format(ChatResponse(
                            content=f"💬 거부 사유를 반영하여 재시도 중...",
                            status=StreamStatus.PROGRESS,
                        ))

                    elif approved:
                        if interrupted_info:
                            tool_names = interrupted_info["tools"]
                            display_name = ", ".join(tool_names)
                            yield SSEFormatter.format(ChatResponse(
                                content=f"⚡ {display_name} 실행 중...",
                                status=StreamStatus.PROGRESS,
                            ))

                        resume_value = {"decisions": [{"type": "approve"} for _ in range(tool_count)]}
                    else:
                        resume_value = {"decisions": [{"type": "reject", "message": "사용자가 도구 실행을 거부했습니다."} for _ in range(tool_count)]}

                    input_data = Command(resume=resume_value)

                # 공통: agent stream 실행
                configurable = {"thread_id": thread_id}
                if checkpoint_id:
                    configurable["checkpoint_id"] = checkpoint_id
                config = {
                    "configurable": configurable,
                    "recursion_limit": 100,
                }
                context = ChatContext(
                    thread_id=thread_id,
                    token=token,
                )

                async for sse_msg in self._run_agent_stream(
                    main_agent, input_data, config, context, thread_id, span, result,
                ):
                    yield sse_msg

                if not result.is_confirm and not result.error:
                    span.set_status(StatusCode.OK)
                    if is_new_chat:
                        logger.info(f"✅ 오케스트레이터 실행 완료: 응답 길이={len(result.ai_response)}")

            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                action = "실행" if is_new_chat else "resume"
                logger.error(f"❌ Orchestrator {action} 에러: {e}")
                result.error = str(e)

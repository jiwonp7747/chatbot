"""
오케스트레이터 - Subagents 패턴

메인 에이전트가 서브에이전트(RAG, Tool)를 도구로 사용합니다.
각 서브에이전트는 agents/ 패키지에서 정의되며, as_tool()로 도구화됩니다.

흐름:
  사용자 요청 → 메인 에이전트 → 서브에이전트 선택/호출 → 결과 반환 → 최종 응답
  (HITL 활성화 시: 도구 호출 전 interrupt → 사용자 확인 → resume)

구조:
  메인 에이전트 (라우팅 + 응답 생성)
    ├── search_documents → RagAgent (tag_search, semantic_search)
    ├── execute_tools    → ToolAgent (MCP 도구들)
    └── 직접 응답 (도구 불필요시)
"""
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage

from opentelemetry import trace as otel_trace
from opentelemetry.trace import StatusCode

from ai.agents import RagAgent, ToolAgent
from ai.graph.schema.graph_state import ChatGraphState
from ai.graph.schema.stream import ChatResponse, StreamStatus
from ai.graph.nodes import load_chat_history_node
from ai.tools.mcp.wrapper import wrap_mcp_tools
from util.sse_formatter import SSEFormatter

logger = logging.getLogger("chat-server")

# 모듈 싱글턴: 모든 thread의 체크포인트를 공유
_checkpointer = InMemorySaver()
# 모델별 에이전트 캐시 (매 요청마다 재빌드 방지)
_agent_cache: dict[str, object] = {}
# HITL interrupt 시 도구 이름 보관 (thread_id → tool_name)
_interrupted_tools: dict[str, str] = {}

MAIN_AGENT_PROMPT = """당신은 AI 어시스턴트 오케스트레이터입니다.
사용자의 요청을 분석하여 적절한 전문가에게 위임하세요.

사용 가능한 전문가:
- search_documents: 업로드된 문서에서 정보를 검색합니다. 문서 관련 질문에 사용하세요.
- execute_tools: 차트 생성, 메모리 저장 등 외부 도구를 실행합니다.

판단 기준:
1. 문서 검색이 필요한 경우 → search_documents 호출
2. 차트/시각화/메모리 등 도구가 필요한 경우 → execute_tools 호출
3. 일반 대화, 번역, 코드 작성 등 → 도구 없이 직접 답변

중요 규칙:
- 한 턴에 도구를 최대 3번까지만 호출하세요. 여러 도구를 동시에 호출하지 마세요.
- 도구 결과가 부족해도 추가 호출 없이 가진 정보로 답변하세요.

전문가의 결과를 바탕으로 사용자에게 자연스러운 최종 답변을 제공하세요.
"""

# 도구 이름 → 진행 메시지 매핑
_TOOL_PROGRESS_LABELS = {
    "search_documents": "📖 문서 검색 에이전트가 작업 중입니다...",
    "execute_tools": "⚡ 도구 실행 에이전트가 작업 중입니다...",
}


class Orchestrator:
    """Subagents 패턴 오케스트레이터

    각 서브에이전트는 agents/ 패키지에서 build() + as_tool()로 정의됩니다.
    오케스트레이터는 as_tool()로 받은 도구를 메인 에이전트에 전달할 뿐입니다.
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

    async def _get_or_build_agent(self, model_string: str):
        """에이전트 캐시에서 가져오거나 새로 빌드"""
        if model_string in _agent_cache:
            return _agent_cache[model_string]

        agent = await self._build_main_agent(model_string)
        _agent_cache[model_string] = agent
        return agent

    async def _build_main_agent(self, model_string: str):
        """서브에이전트 도구를 수집하고 메인 에이전트 생성"""
        mcp_tools = await self._load_mcp_tools()

        # 서브에이전트 → 도구로 변환
        rag = RagAgent(model=model_string)
        subagent_tools = [rag.as_tool()]

        if mcp_tools:
            tool_ag = ToolAgent(model=model_string, mcp_tools=mcp_tools)
            subagent_tools.append(tool_ag.as_tool())

        logger.info(f"🤖 서브에이전트 도구 {len(subagent_tools)}개 구성 완료")

        # 메인 에이전트 (싱글턴 checkpointer 사용)
        return create_agent(
            model=model_string,
            tools=subagent_tools,
            middleware=[
                HumanInTheLoopMiddleware(
                    interrupt_on={
                        "search_documents": True,
                    },
                    description_prefix="도구 실행 승인 필요",
                ),
            ],
            checkpointer=_checkpointer,
            system_prompt=MAIN_AGENT_PROMPT,
        )

    @staticmethod
    def _resolve_model_string(state: ChatGraphState) -> str:
        """상태에서 create_agent용 모델 문자열 생성"""
        provider = state.get("provider", "openai").lower()
        api_model = state.get("api_model", "gpt-4o-mini")
        return f"{provider}:{api_model}"

    @staticmethod
    def _build_messages(state: ChatGraphState) -> list:
        """상태에서 LangChain 메시지 리스트 구성"""
        messages = []

        for msg in state.get("message_history", []):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        # 사용자 메시지 (RAG 태그가 있으면 힌트 추가)
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
                return msg.content
        if messages and hasattr(messages[-1], "content"):
            return messages[-1].content
        return ""

    async def run_until_stream(
        self, initial_state: ChatGraphState, thread_id: str
    ) -> AsyncGenerator[tuple[Optional[str], Optional[ChatGraphState]], None]:
        """SSE 스트리밍 인터페이스 (HITL interrupt 지원)

        Yields:
            - 중간 진행: (SSE 메시지, None)
            - CONFIRM 이벤트: (SSE CONFIRM 메시지, None) → 스트림 종료
            - 최종 완료: (None, final_state)  ← ai_response 포함
        """
        tracer = otel_trace.get_tracer("chat-backend")

        with tracer.start_as_current_span("orchestrator.run") as span:
            span.set_attribute("thread.id", thread_id)

            try:
                # 1. 대화 기록 로드
                progress = ChatResponse(
                    content="📚 대화 기록을 불러오고 있습니다...",
                    status=StreamStatus.PROGRESS,
                )
                yield (SSEFormatter.format(progress), None)
                history_result = await load_chat_history_node(initial_state, self.db)
                state = {**initial_state, **history_result}

                # 2. 메인 에이전트 구성
                model_string = self._resolve_model_string(state)
                span.set_attribute("model", model_string)
                progress = ChatResponse(
                    content="🔧 전문가 에이전트를 준비하고 있습니다...",
                    status=StreamStatus.PROGRESS,
                )
                yield (SSEFormatter.format(progress), None)

                main_agent = await self._get_or_build_agent(model_string)
                logger.info(f"🤖 메인 에이전트 준비 완료: model={model_string}")

                # 3. 메시지 구성 + 실행
                messages = self._build_messages(state)

                progress = ChatResponse(
                    content="🤖 생각 중입니다...",
                    status=StreamStatus.PROGRESS,
                )
                yield (SSEFormatter.format(progress), None)

                # 4. astream(stream_mode="updates")로 진행 상황 캡처
                ai_response = ""
                config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 25,
                }

                async for chunk in main_agent.astream(
                    {"messages": messages},
                    config=config,
                    stream_mode="updates",
                ):
                    # interrupt 감지 — Interrupt 객체: .value (dict), .id (str)
                    if "__interrupt__" in chunk:
                        interrupt = chunk["__interrupt__"][0]
                        action_requests = interrupt.value.get("action_requests", [])
                        if action_requests:
                            first_action = action_requests[0]
                            tool_name = first_action.get("name", "unknown")
                            tool_args = first_action.get("args", {})
                        else:
                            tool_name = "unknown"
                            tool_args = {}

                        confirm = ChatResponse(
                            content=f"'{tool_name}' 도구를 실행하시겠습니까?",
                            status=StreamStatus.CONFIRM,
                            thread_id=thread_id,
                            tool_name=tool_name,
                            tool_args=tool_args,
                        )
                        # OTEL: interrupt는 에러가 아닌 정상 흐름
                        span.set_attribute("hitl.interrupted", True)
                        span.set_attribute("hitl.tool_name", tool_name)
                        span.set_status(StatusCode.OK, "HITL interrupt")
                        _interrupted_tools[thread_id] = tool_name
                        yield (SSEFormatter.format(confirm), None)
                        logger.info(f"⏸️ HITL interrupt: tool={tool_name}, thread={thread_id}")
                        return  # SSE 스트림 종료, 프론트에서 resume 대기

                    # 일반 노드 실행 결과 처리
                    for key, value in chunk.items():
                        if key == "model":
                            msgs = value.get("messages", [])
                            for msg in msgs:
                                # 도구 호출 의도 감지 → progress 전송
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        tc_name = tc.get("name", "unknown")
                                        label = _TOOL_PROGRESS_LABELS.get(
                                            tc_name, f"⚡ {tc_name} 실행 중..."
                                        )
                                        progress = ChatResponse(
                                            content=label,
                                            status=StreamStatus.PROGRESS,
                                        )
                                        yield (SSEFormatter.format(progress), None)

                                # 최종 AI 응답 캡처
                                if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                                    ai_response = msg.content

                        elif key == "tools":
                            # 도구 실행 완료 로그
                            msgs = value.get("messages", [])
                            for msg in msgs:
                                if hasattr(msg, "name"):
                                    logger.info(f"✅ 서브에이전트 완료: {msg.name}")

                # 5. 최종 상태
                final_state = {**state, "ai_response": ai_response}
                span.set_status(StatusCode.OK)
                logger.info(f"✅ 오케스트레이터 실행 완료: 응답 길이={len(ai_response)}")

                yield (None, final_state)

            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                logger.error(f"❌ Orchestrator 실행 에러: {e}")
                yield (None, {**initial_state, "error": str(e)})

    async def resume_stream(
        self, thread_id: str, approved: bool, model_string: str
    ) -> AsyncGenerator[tuple[Optional[str], Optional[ChatGraphState]], None]:
        """HITL 재개 - 사용자 승인/거부 후 그래프 실행 계속

        Yields:
            - CONFIRM (연쇄 interrupt): (SSE CONFIRM 메시지, None)
            - 최종 완료: (None, {"ai_response": ...})
        """
        tracer = otel_trace.get_tracer("chat-backend")

        with tracer.start_as_current_span("orchestrator.resume") as span:
            span.set_attribute("thread.id", thread_id)
            span.set_attribute("hitl.approved", approved)
            span.set_attribute("model", model_string)

            try:
                main_agent = await self._get_or_build_agent(model_string)

                # interrupt 시 저장해둔 도구 이름으로 진행 메시지 전송
                interrupted_tool = _interrupted_tools.pop(thread_id, None)
                if interrupted_tool and approved:
                    label = _TOOL_PROGRESS_LABELS.get(
                        interrupted_tool, f"⚡ {interrupted_tool} 실행 중..."
                    )
                    progress = ChatResponse(
                        content=label,
                        status=StreamStatus.PROGRESS,
                    )
                    yield (SSEFormatter.format(progress), None)

                if approved:
                    resume_value = {"decisions": [{"type": "approve"}]}
                else:
                    resume_value = {"decisions": [{"type": "reject", "message": "사용자가 도구 실행을 거부했습니다."}]}
                config = {
                    "configurable": {"thread_id": thread_id},
                    "recursion_limit": 25,
                }

                ai_response = ""

                async for chunk in main_agent.astream(
                    Command(resume=resume_value),
                    config=config,
                    stream_mode="updates",
                ):
                    # 연쇄 interrupt (다른 도구 호출) 처리
                    if "__interrupt__" in chunk:
                        interrupt = chunk["__interrupt__"][0]
                        action_requests = interrupt.value.get("action_requests", [])
                        if action_requests:
                            first_action = action_requests[0]
                            tool_name = first_action.get("name", "unknown")
                            tool_args = first_action.get("args", {})
                        else:
                            tool_name = "unknown"
                            tool_args = {}

                        confirm = ChatResponse(
                            content=f"'{tool_name}' 도구를 실행하시겠습니까?",
                            status=StreamStatus.CONFIRM,
                            thread_id=thread_id,
                            tool_name=tool_name,
                            tool_args=tool_args,
                        )
                        # OTEL: 연쇄 interrupt도 정상 흐름
                        span.set_attribute("hitl.chained_interrupt", True)
                        span.set_attribute("hitl.tool_name", tool_name)
                        span.set_status(StatusCode.OK, "Chained HITL interrupt")
                        yield (SSEFormatter.format(confirm), None)
                        logger.info(f"⏸️ HITL 연쇄 interrupt: tool={tool_name}, thread={thread_id}")
                        return

                    for key, value in chunk.items():
                        if key == "model":
                            msgs = value.get("messages", [])
                            for msg in msgs:
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        tc_name = tc.get("name", "unknown")
                                        label = _TOOL_PROGRESS_LABELS.get(
                                            tc_name, f"⚡ {tc_name} 실행 중..."
                                        )
                                        progress = ChatResponse(
                                            content=label,
                                            status=StreamStatus.PROGRESS,
                                        )
                                        yield (SSEFormatter.format(progress), None)

                                if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                                    ai_response = msg.content

                        elif key == "tools":
                            msgs = value.get("messages", [])
                            for msg in msgs:
                                if hasattr(msg, "name"):
                                    logger.info(f"✅ 서브에이전트 완료: {msg.name}")

                span.set_status(StatusCode.OK)
                yield (None, {"ai_response": ai_response})

            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                span.record_exception(e)
                logger.error(f"❌ Orchestrator resume 에러: {e}")
                yield (None, {"ai_response": "", "error": str(e)})

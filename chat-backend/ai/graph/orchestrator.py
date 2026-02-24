"""
오케스트레이터 - Subagents 패턴

메인 에이전트가 서브에이전트(RAG, Tool)를 도구로 사용합니다.
각 서브에이전트는 agents/ 패키지에서 정의되며, as_tool()로 도구화됩니다.

흐름:
  사용자 요청 → 메인 에이전트 → 서브에이전트 선택/호출 → 결과 반환 → 최종 응답

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
from langchain_core.messages import HumanMessage, AIMessage

from ai.agents import RagAgent, ToolAgent
from ai.graph.schema.graph_state import ChatGraphState
from ai.graph.schema.stream import ChatResponse, StreamStatus
from ai.graph.nodes import load_chat_history_node
from ai.tools.mcp.wrapper import wrap_mcp_tools
from util.sse_formatter import SSEFormatter

logger = logging.getLogger("chat-server")

MAIN_AGENT_PROMPT = """당신은 AI 어시스턴트 오케스트레이터입니다.
사용자의 요청을 분석하여 적절한 전문가에게 위임하세요.

사용 가능한 전문가:
- search_documents: 업로드된 문서에서 정보를 검색합니다. 문서 관련 질문에 사용하세요.
- execute_tools: 차트 생성, 메모리 저장 등 외부 도구를 실행합니다.

판단 기준:
1. 문서 검색이 필요한 경우 → search_documents 호출
2. 차트/시각화/메모리 등 도구가 필요한 경우 → execute_tools 호출
3. 일반 대화, 번역, 코드 작성 등 → 도구 없이 직접 답변

전문가의 결과를 바탕으로 사용자에게 자연스러운 최종 답변을 제공하세요.
"""


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

        # 메인 에이전트
        return create_agent(
            model=model_string,
            tools=subagent_tools,
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
        self, initial_state: ChatGraphState
    ) -> AsyncGenerator[tuple[Optional[str], Optional[ChatGraphState]], None]:
        """SSE 스트리밍 인터페이스

        Yields:
            - 중간 진행: (SSE 메시지, None)
            - 최종 완료: (None, final_state)  ← ai_response 포함
        """
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
            progress = ChatResponse(
                content="🔧 전문가 에이전트를 준비하고 있습니다...",
                status=StreamStatus.PROGRESS,
            )
            yield (SSEFormatter.format(progress), None)

            main_agent = await self._build_main_agent(model_string)
            logger.info(f"🤖 메인 에이전트 생성 완료: model={model_string}")

            # 3. 메시지 구성 + 실행
            messages = self._build_messages(state)

            progress = ChatResponse(
                content="🤖 요청을 분석하고 적절한 전문가를 선택하고 있습니다...",
                status=StreamStatus.PROGRESS,
            )
            yield (SSEFormatter.format(progress), None)

            # 4. astream_events로 진행 상황 캡처
            ai_response = ""

            async for event in main_agent.astream_events(
                {"messages": messages}, version="v2"
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_labels = {
                        "search_documents": "📖 문서 검색 에이전트가 작업 중입니다...",
                        "execute_tools": "⚡ 도구 실행 에이전트가 작업 중입니다...",
                    }
                    label = tool_labels.get(tool_name, f"⚡ {tool_name} 실행 중...")
                    progress = ChatResponse(
                        content=label, status=StreamStatus.PROGRESS,
                    )
                    yield (SSEFormatter.format(progress), None)

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    logger.info(f"✅ 서브에이전트 완료: {tool_name}")

                elif kind == "on_chat_model_end":
                    output = event.get("data", {}).get("output", None)
                    if output and hasattr(output, "content") and output.content:
                        ai_response = output.content

            # 5. 최종 상태
            final_state = {**state, "ai_response": ai_response}
            logger.info(f"✅ 오케스트레이터 실행 완료: 응답 길이={len(ai_response)}")

            yield (None, final_state)

        except Exception as e:
            logger.error(f"❌ Orchestrator 실행 에러: {e}")
            yield (None, {**initial_state, "error": str(e)})

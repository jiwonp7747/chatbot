"""
LangGraph 기반 채팅 서비스

대화 처리를 여러 단계로 나누어 관리하는 LangGraph 구현
확장성과 유지보수성을 위해 각 단계를 독립적인 노드로 분리
"""
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from langchain_core.exceptions import ErrorCode
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, END

from common.exception.api_exception import ApiException
from common.response.code import FailureCode
from schema import ChatRequest, ChatResponse, StreamStatus
from schema.chat_graph_schema import ChatGraphState
from sse.sse_util import SSEFormatter
from middleware.stream_tracker import (
    register_stream,
    set_user_chat_time,
    get_stream_data
)
from db.database import get_db

from .nodes import (
    load_available_tools_node,
    load_chat_history_node,
    analyze_intent_node,
    call_tools_node,
    generate_response_node,
    stream_response_node
)
from .chat_serivce import save_chat_to_db  # 기존 DB 저장 로직 재사용

logger = logging.getLogger("chat-server")


class ChatLangGraph:
    """
    LangGraph 기반 채팅 처리 클래스

    노드 구성:
    0. load_available_tools: MCP 서버에서 사용 가능한 도구 목록 조회
    1. load_history: 대화 기록 로드
    2. analyze_intent: 사용자 의도 분석 + 사용 가능한 도구 중 필요한 도구 파악
    3. call_tools: MCP 도구 호출
    4. generate_response: 메시지 구성 + 추가 도구 필요 여부 판단
    5. stream_response: 응답 스트리밍 (별도 처리)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        LangGraph 워크플로우 구성

        Returns:
            구성된 StateGraph
        """
        # StateGraph 생성
        workflow = StateGraph(ChatGraphState)

        # 노드 추가 (stream_response는 별도 처리)
        workflow.add_node("load_available_tools", self._wrap_load_available_tools)
        workflow.add_node("load_history", self._wrap_load_history)
        workflow.add_node("analyze_intent", self._wrap_analyze_intent)
        workflow.add_node("call_tools", self._wrap_call_tools)
        workflow.add_node("generate_response", self._wrap_generate_response)

        # 엣지 연결
        workflow.set_entry_point("load_available_tools")
        workflow.add_edge("load_available_tools", "load_history")
        workflow.add_edge("load_history", "analyze_intent")
        workflow.add_edge("analyze_intent", "call_tools")
        workflow.add_edge("call_tools", "generate_response")

        # 조건부 라우팅: generate_response → call_tools (반복) 또는 END
        workflow.add_conditional_edges(
            "generate_response",
            self._should_continue,
            {
                "call_tools": "call_tools",
                "end": END
            }
        )

        return workflow.compile()

    @staticmethod
    def _should_continue(state: ChatGraphState) -> str:
        """
        추가 도구 호출이 필요한지 판단하는 조건부 라우팅 함수

        Args:
            state: 현재 그래프 상태

        Returns:
            다음 노드 이름 ("call_tools" 또는 "end")
        """
        needs_more_tools = state.get("needs_more_tools", False)
        iteration_count = state.get("iteration_count", 0)

        # 최대 5회 반복 제한
        if needs_more_tools and iteration_count < 5:
            logger.info(f"🔄 추가 도구 호출 필요 (반복 {iteration_count}/5)")
            return "call_tools"
        else:
            if iteration_count >= 5:
                logger.warning("⚠️ 최대 반복 횟수 도달 - 응답 생성으로 이동")
            return "end"

    async def _wrap_load_available_tools(self, state: ChatGraphState) -> ChatGraphState:
        """load_available_tools 노드 래퍼"""
        result = await load_available_tools_node(state)
        return {**state, **result}

    async def _wrap_load_history(self, state: ChatGraphState) -> ChatGraphState:
        """load_history 노드 래퍼 (DB 세션 전달)"""
        result = await load_chat_history_node(state, self.db)
        return {**state, **result}

    async def _wrap_analyze_intent(self, state: ChatGraphState) -> ChatGraphState:
        """analyze_intent 노드 래퍼"""
        result = await analyze_intent_node(state)
        return {**state, **result}

    async def _wrap_call_tools(self, state: ChatGraphState) -> ChatGraphState:
        """call_tools 노드 래퍼"""
        result = await call_tools_node(state)
        return {**state, **result}

    async def _wrap_generate_response(self, state: ChatGraphState) -> ChatGraphState:
        """generate_response 노드 래퍼"""
        result = await generate_response_node(state)
        return {**state, **result}

    async def run_until_stream(
        self,
        initial_state: ChatGraphState
    ) -> ChatGraphState:
        """
        스트리밍 전까지 그래프 실행 (load_available_tools → load_history → analyze_intent → call_tools → generate_response)

        Args:
            initial_state: 초기 상태

        Returns:
            스트리밍 준비가 완료된 상태
        """
        try:
            # 그래프 실행
            final_state = await self.graph.ainvoke(initial_state)
            return final_state

        except Exception as e:
            logger.error(f"❌ LangGraph 실행 에러: {e}")
            return {
                **initial_state,
                "error": str(e)
            }


async def process_chat_with_langgraph(
    request: ChatRequest,
    db: AsyncSession,
    http_request: Request,
) -> AsyncGenerator[str, None]:
    """
    LangGraph를 사용한 채팅 처리 메인 함수

    Args:
        request: 채팅 요청
        db: 데이터베이스 세션
        http_request: HTTP 요청 객체

    Yields:
        SSE 형식의 응답 청크
    """
    # 스트림 ID 가져오기
    stream_id = getattr(http_request.state, 'stream_id', None)
    if not stream_id:
        logger.error("❌ stream_id가 없습니다!")
        raise RuntimeError("stream_id not found in request.state")

    auth_header = http_request.headers.get("authorization")
    logger.info("auth_header: %s", auth_header)
    if not auth_header:
        logger.error("❌ 인증 토큰이 존재하지 않습니다.")
        error_response = ChatResponse(
            content="인증 토큰이 누락되었습니다.",
            status=StreamStatus.ERROR,
            error=FailureCode.UNAUTHORIZED.message()
        )
        yield SSEFormatter.format(error_response)
        return  # 함수 종료

    user_chat_created_at = datetime.utcnow()

    # DB 저장 콜백 함수 정의
    async def save_callback():
        """Middleware cleanup에서 호출될 DB 저장 함수"""
        stream_data = get_stream_data(stream_id)
        if not stream_data:
            logger.warning(f"⚠️ Stream data 없음: {stream_id}")
            return

        collected_content = stream_data.get("collected_content", "")
        user_time = stream_data.get("user_chat_created_at")

        if collected_content:
            logger.info(f"💾 Callback 저장 시작작: {stream_id}, length: {len(collected_content)}")

            # 새로운 독립적인 DB 세션 생성
            async for new_db in get_db():
                try:
                    await save_chat_to_db(request, collected_content, user_time, new_db)
                except ApiException as api_exception:
                    logger.error(f"❌ Callback DB 저장 실패: {api_exception.message}")
                except Exception as e:
                    logger.error(f"❌ Callback DB 저장 실패: {stream_id}, {e}")
                finally:
                    await new_db.close()
                break

    # 스트림 등록
    register_stream(stream_id, save_callback)
    set_user_chat_time(stream_id, user_chat_created_at)

    try:
        # 1. LangGraph 초기화
        chat_graph = ChatLangGraph(db)

        # 2. 초기 상태 구성
        initial_state: ChatGraphState = {
            "chat_session_id": request.chat_session_id,
            "user_prompt": request.prompt,
            "model": request.model or "gpt-5.1-mini",
            "message_history": [],
            "intent_analysis": None,
            "available_tools": [],
            "tools_to_call": [],
            "tool_results": [],
            "needs_more_tools": False,
            "iteration_count": 0,
            "messages": [],
            "ai_response": "",
            "user_chat_created_at": user_chat_created_at,
            "token": auth_header,
            "stream_id": stream_id,
            "error": None,
        }

        # 3. 그래프 실행 (스트리밍 전까지)
        logger.info(f"🚀 LangGraph 실행 시작: {stream_id}")
        final_state = await chat_graph.run_until_stream(initial_state)

        # 4. 에러 체크
        if final_state.get("error"):
            error_response = ChatResponse(
                content="",
                status=StreamStatus.ERROR,
                error=final_state["error"]
            )
            yield SSEFormatter.format(error_response)
            return

        # 5. 응답 스트리밍 (노드 4 실행)
        logger.info(f"📡 응답 스트리밍 시작: {stream_id}")
        async for chunk in stream_response_node(final_state, http_request):
            yield chunk

    except Exception as e:
        logger.error(f"❌ LangGraph 처리 에러: {stream_id}, {e}")

        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)

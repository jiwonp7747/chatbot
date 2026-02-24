"""
LangGraph 기반 채팅 서비스

그래프 실행, SSE 스트리밍, DB 저장 등 비즈니스 로직을 담당합니다.
Subagents 패턴 오케스트레이터: graph/orchestrator.py
"""
import logging
from datetime import datetime
from typing import AsyncGenerator

from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.api_exception import ApiException
from common.response.code import FailureCode
from ai.graph.schema.stream import ChatRequest, ChatResponse, StreamStatus
from ai.graph.schema.graph_state import ChatGraphState
from ai.graph.orchestrator import Orchestrator
from ai.graph.nodes import stream_response_node
from util.sse_formatter import SSEFormatter
from middleware.stream_tracker import (
    register_stream,
    set_user_chat_time,
    get_stream_data,
    update_stream_content,
)
from db.database import get_db

from .chat_service import save_chat_to_db  # 기존 DB 저장 로직 재사용
from .model_resolver import resolve_model_config

logger = logging.getLogger("chat-server")


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
            logger.info(f"💾 Callback 저장 시작: {stream_id}, length: {len(collected_content)}")

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
        resolved_model = await resolve_model_config(db, request.model)

        # 1. 오케스트레이터 초기화 (Subagents 패턴)
        orchestrator = Orchestrator(db)

        # 2. 초기 상태 구성
        initial_state: ChatGraphState = {
            "chat_session_id": request.chat_session_id,
            "user_prompt": request.prompt,
            "model": resolved_model.model_key,
            "api_model": resolved_model.api_model,
            "provider": resolved_model.provider,
            "message_history": [],
            "intent_analysis": None,
            "available_tools": [],
            "tools_to_call": [],
            "tool_results": [],
            "needs_more_tools": False,
            "iteration_count": 0,
            "rag_tags": request.rag_tags if request.rag_tags else [],
            "rag_results": [],
            "messages": [],
            "ai_response": "",
            "user_chat_created_at": user_chat_created_at,
            "token": auth_header,
            "stream_id": stream_id,
            "error": None,
        }

        # 3. 오케스트레이터 실행 - 에이전트가 도구 선택/호출/응답 생성을 자동 처리
        logger.info(f"🚀 Orchestrator 실행 시작: {stream_id}")

        final_state = None
        async for progress_message, state in orchestrator.run_until_stream(initial_state):
            # 중간 진행 메시지 전송
            if progress_message:
                logger.info(f"🚀 클라이언트로 진행 메시지 전송 중... (길이: {len(progress_message)})")
                yield progress_message
                logger.info(f"✅ 진행 메시지 전송 완료")

            # 최종 state 저장
            if state:
                logger.info(f"📦 최종 state 수신 완료")
                final_state = state

        # 4. 에러 체크
        if not final_state:
            error_response = ChatResponse(
                content="",
                status=StreamStatus.ERROR,
                error="오케스트레이터 실행 중 최종 상태를 받지 못했습니다."
            )
            yield SSEFormatter.format(error_response)
            return

        if final_state.get("error"):
            error_response = ChatResponse(
                content="",
                status=StreamStatus.ERROR,
                error=final_state["error"]
            )
            yield SSEFormatter.format(error_response)
            return

        # 5. 응답 스트리밍
        logger.info(f"📡 응답 스트리밍 시작: {stream_id}")

        ai_response = final_state.get("ai_response", "")
        if ai_response:
            # Subagents 패턴: 에이전트가 이미 응답을 생성했으므로 청크 단위로 스트리밍
            chunk_size = 64
            for i in range(0, len(ai_response), chunk_size):
                if await http_request.is_disconnected():
                    logger.info(f"🔌 클라이언트 연결 끊김: {stream_id}")
                    return

                chunk = ai_response[i:i + chunk_size]
                if stream_id:
                    update_stream_content(stream_id, chunk)

                response = ChatResponse(
                    content=chunk,
                    status=StreamStatus.STREAMING,
                )
                yield SSEFormatter.format(response)

            # 완료
            done_response = ChatResponse(content="", status=StreamStatus.DONE)
            yield SSEFormatter.format(done_response)
            logger.info(f"✅ 스트리밍 정상 완료: {stream_id}")
        else:
            # fallback: 기존 방식 (stream_response_node가 LLM 직접 호출)
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
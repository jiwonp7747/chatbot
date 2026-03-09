"""
LangGraph 기반 채팅 서비스

그래프 실행, SSE 스트리밍, DB 저장 등 비즈니스 로직을 담당합니다.
Subagents 패턴 오케스트레이터: graph/orchestrator.py
"""
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.response.code import FailureCode
from ai.graph.schema.stream import ChatRequest, ChatResponse, StreamStatus, ResumeRequest, StreamResult
from ai.graph.schema.graph_state import ChatGraphState
from ai.graph.orchestrator import Orchestrator
from util.sse_formatter import SSEFormatter

from .chat_service import save_user_message_to_db, save_ai_message_to_db
from .model_resolver import resolve_model_config

logger = logging.getLogger("chat-server")

# HITL 대기 중인 원본 요청 정보 (thread_id → {request, user_chat_created_at})
# interrupt 후 resume 시 DB 저장에 사용
_hitl_pending_requests: dict[str, dict] = {}

_STREAM_CHUNK_SIZE = 64


class _ClientDisconnectedError(Exception):
    """SSE 스트리밍 중 클라이언트 연결 종료 예외."""


def _format_error_sse(error: str, content: str = "") -> str:
    return SSEFormatter.format(
        ChatResponse(
            content=content,
            status=StreamStatus.ERROR,
            error=error,
        )
    )


def _format_done_sse() -> str:
    return SSEFormatter.format(ChatResponse(content="", status=StreamStatus.DONE))


def _build_initial_state(
    request: ChatRequest,
    resolved_model,
    user_chat_created_at: datetime,
    thread_id: str,
) -> ChatGraphState:
    return {
        "user_prompt": request.prompt,
        "model": resolved_model.model_key,
        "api_model": resolved_model.api_model,
        "provider": resolved_model.provider,
        "intent_analysis": None,
        "available_tools": [],
        "tools_to_call": [],
        "tool_results": [],
        "needs_more_tools": False,
        "iteration_count": 0,
        "rag_tags": request.rag_tags if request.rag_tags else [],
        "rag_results": [],
        "ai_response": "",
        "user_chat_created_at": user_chat_created_at,
        "thread_id": thread_id,
        "error": None,
    }


async def _resolve_model_string(db: AsyncSession, requested_model: Optional[str]) -> str:
    resolved_model = await resolve_model_config(db, requested_model)
    provider = resolved_model.provider.lower()
    provider = Orchestrator._LANGCHAIN_PROVIDER_MAP.get(provider, provider)
    return f"{provider}:{resolved_model.api_model}"


async def _yield_ai_stream_chunks(
    ai_response: str,
    http_request: Request,
    thread_id: str,
    log_context: str,
) -> AsyncGenerator[str, None]:
    for i in range(0, len(ai_response), _STREAM_CHUNK_SIZE):
        if await http_request.is_disconnected():
            logger.info(f"🔌 {log_context} 클라이언트 연결 끊김: {thread_id}")
            raise _ClientDisconnectedError()

        chunk = ai_response[i:i + _STREAM_CHUNK_SIZE]
        response = ChatResponse(
            content=chunk,
            status=StreamStatus.STREAMING,
        )
        yield SSEFormatter.format(response)


async def process_chat(
    request: ChatRequest | ResumeRequest,
    db: AsyncSession,
    http_request: Request,
) -> AsyncGenerator[str, None]:
    """통합 채팅 처리 — 신규 채팅과 HITL resume 모두 처리

    Args:
        request: ChatRequest (신규) 또는 ResumeRequest (HITL 재개)
        db: 데이터베이스 세션
        http_request: HTTP 요청 객체

    Yields:
        SSE 형식의 응답 청크
    """
    is_resume = isinstance(request, ResumeRequest)
    thread_id = str(uuid.uuid4())
    pending = None
    user_chat_created_at = None

    try:
        orchestrator = Orchestrator(db)
        result = StreamResult()

        if is_resume:
            # --- HITL resume ---
            pending = _hitl_pending_requests.pop(request.thread_id, None)
            if not pending:
                logger.warning(f"⚠️ HITL 원본 요청 정보 없음: {request.thread_id}")

            model_string = await _resolve_model_string(db, request.model)
            auth_header = http_request.headers.get("authorization")

            async for sse_msg in orchestrator.run(
                thread_id=request.thread_id,
                result=result,
                chat_session_id=request.chat_session_id,
                token=auth_header,
                approved=request.approved,
                model_string=model_string,
                edit_message=request.edit_message,
                edited_tool_calls=request.edited_tool_calls,
            ):
                yield sse_msg

            thread_id = request.thread_id  # 로깅용

        else:
            # --- 신규 채팅 ---
            auth_header = http_request.headers.get("authorization")
            logger.info("auth_header: %s", auth_header)
            if not auth_header:
                logger.error("❌ 인증 토큰이 존재하지 않습니다.")
                yield SSEFormatter.format(ChatResponse(
                    content="인증 토큰이 누락되었습니다.",
                    status=StreamStatus.ERROR,
                    error=FailureCode.UNAUTHORIZED.message()
                ))
                return

            user_chat_created_at = datetime.utcnow()
            await save_user_message_to_db(request.chat_session_id, request.prompt, user_chat_created_at)

            resolved_model = await resolve_model_config(db, request.model)
            initial_state = _build_initial_state(
                request=request,
                resolved_model=resolved_model,
                user_chat_created_at=user_chat_created_at,
                thread_id=thread_id,
            )

            logger.info(f"🚀 Orchestrator 실행 시작: {thread_id}")

            async for sse_msg in orchestrator.run(
                thread_id=thread_id,
                result=result,
                chat_session_id=request.chat_session_id,
                token=auth_header,
                initial_state=initial_state,
            ):
                yield sse_msg

        # --- 공통 후처리 ---

        # HITL CONFIRM → pending 보관 후 종료
        if result.is_confirm:
            if is_resume:
                if pending:
                    _hitl_pending_requests[request.thread_id] = pending
                logger.info(f"⏸️ 연쇄 HITL confirm, 다음 resume 대기: {request.thread_id}")
            else:
                _hitl_pending_requests[thread_id] = {
                    "request": request,
                    "user_chat_created_at": user_chat_created_at,
                }
                logger.info(f"⏸️ HITL confirm 전송 완료, resume 대기: {thread_id}")
            return

        # 에러 체크
        if result.error:
            yield _format_error_sse(result.error)
            return

        # 응답 스트리밍
        if result.ai_response:
            try:
                async for chunk_sse in _yield_ai_stream_chunks(
                    ai_response=result.ai_response,
                    http_request=http_request,
                    thread_id=thread_id,
                    log_context="resume 중" if is_resume else "",
                ):
                    yield chunk_sse
            except _ClientDisconnectedError:
                return

            # DB 저장: resume일 때는 pending이 있을 때만
            if not is_resume or pending:
                await save_ai_message_to_db(
                    request.chat_session_id,
                    result.ai_response,
                )

            yield _format_done_sse()
            logger.info(f"✅ {'HITL resume' if is_resume else '스트리밍'} 완료: {thread_id}")
        else:
            if is_resume:
                yield _format_done_sse()
                logger.info(f"✅ HITL resume 완료 (응답 없음): {thread_id}")
            else:
                yield _format_error_sse("에이전트로부터 응답을 받지 못했습니다.")

    except Exception as e:
        action = "HITL resume" if is_resume else "LangGraph 처리"
        logger.error(f"❌ {action} 에러: {thread_id}, {e}")
        yield _format_error_sse(str(e))

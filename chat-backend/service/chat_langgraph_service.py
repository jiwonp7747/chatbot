"""
LangGraph 기반 채팅 서비스

그래프 실행, SSE 스트리밍, DB 저장 등 비즈니스 로직을 담당합니다.
Subagents 패턴 오케스트레이터: graph/orchestrator.py
"""
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator

from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.response.code import FailureCode
from ai.graph.schema.stream import ChatRequest, ChatResponse, StreamStatus, ResumeRequest
from ai.graph.schema.graph_state import ChatGraphState
from ai.graph.orchestrator import Orchestrator
from ai.graph.nodes import stream_response_node
from util.sse_formatter import SSEFormatter

from .chat_service import save_user_message_to_db, save_ai_message_to_db
from .model_resolver import resolve_model_config

logger = logging.getLogger("chat-server")

# HITL 대기 중인 원본 요청 정보 (thread_id → {request, user_chat_created_at})
# interrupt 후 resume 시 DB 저장에 사용
_hitl_pending_requests: dict[str, dict] = {}


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
    stream_id = str(uuid.uuid4())

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

    # 사용자 메시지 즉시 저장
    await save_user_message_to_db(request.chat_session_id, request.prompt, user_chat_created_at)

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
        confirm_sent = False
        async for progress_message, state in orchestrator.run_until_stream(initial_state, thread_id=stream_id):
            # 중간 진행 메시지 전송
            if progress_message:
                logger.info(f"🚀 클라이언트로 진행 메시지 전송 중... (길이: {len(progress_message)})")
                yield progress_message
                # CONFIRM 이벤트 감지 → 스트림 종료 (프론트에서 resume 대기)
                if StreamStatus.CONFIRM.value in progress_message:
                    confirm_sent = True
                logger.info(f"✅ 진행 메시지 전송 완료")

            # 최종 state 저장
            if state:
                logger.info(f"📦 최종 state 수신 완료")
                final_state = state

        # HITL CONFIRM 전송 후에는 여기서 종료 (resume 대기)
        if confirm_sent:
            # 원본 요청 정보 보관 → resume 시 DB 저장에 사용
            _hitl_pending_requests[stream_id] = {
                "request": request,
                "user_chat_created_at": user_chat_created_at,
            }
            logger.info(f"⏸️ HITL confirm 전송 완료, resume 대기: {stream_id}")
            return

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
                response = ChatResponse(
                    content=chunk,
                    status=StreamStatus.STREAMING,
                )
                yield SSEFormatter.format(response)

            # AI 응답 저장
            await save_ai_message_to_db(request.chat_session_id, ai_response, request.prompt)

            # 완료
            done_response = ChatResponse(content="", status=StreamStatus.DONE)
            yield SSEFormatter.format(done_response)
            logger.info(f"✅ 스트리밍 정상 완료: {stream_id}")
        else:
            # fallback: 기존 방식 (stream_response_node가 LLM 직접 호출)
            content_parts = []
            async for chunk_str in stream_response_node(final_state, http_request, content_parts):
                yield chunk_str
            if content_parts:
                await save_ai_message_to_db(
                    request.chat_session_id,
                    "".join(content_parts),
                    request.prompt
                )

    except Exception as e:
        logger.error(f"❌ LangGraph 처리 에러: {stream_id}, {e}")

        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)


async def process_resume(
    resume_request: ResumeRequest,
    db: AsyncSession,
    http_request: Request,
) -> AsyncGenerator[str, None]:
    """HITL 재개 처리

    사용자가 도구 실행을 승인/거부한 후 그래프를 재개합니다.
    """
    stream_id = str(uuid.uuid4())

    # HITL 보관된 원본 요청 정보 꺼내기
    pending = _hitl_pending_requests.pop(resume_request.thread_id, None)
    if not pending:
        logger.warning(f"⚠️ HITL 원본 요청 정보 없음: {resume_request.thread_id}")

    try:
        resolved_model = await resolve_model_config(db, resume_request.model)
        provider = resolved_model.provider.lower()
        provider = Orchestrator._LANGCHAIN_PROVIDER_MAP.get(provider, provider)
        model_string = f"{provider}:{resolved_model.api_model}"

        orchestrator = Orchestrator(db)

        async for progress_message, state in orchestrator.resume_stream(
            thread_id=resume_request.thread_id,
            approved=resume_request.approved,
            model_string=model_string,
            chat_session_id=resume_request.chat_session_id,
        ):
            if progress_message:
                yield progress_message

            if state:
                ai_response = state.get("ai_response", "")
                if ai_response:
                    # 청크 단위 스트리밍
                    chunk_size = 64
                    for i in range(0, len(ai_response), chunk_size):
                        if await http_request.is_disconnected():
                            logger.info(f"🔌 resume 중 클라이언트 연결 끊김")
                            return

                        chunk = ai_response[i:i + chunk_size]
                        response = ChatResponse(
                            content=chunk,
                            status=StreamStatus.STREAMING,
                        )
                        yield SSEFormatter.format(response)

                    # AI 응답 저장
                    if pending:
                        await save_ai_message_to_db(
                            resume_request.chat_session_id,
                            ai_response,
                            pending["request"].prompt if pending else "",
                        )

        done_response = ChatResponse(content="", status=StreamStatus.DONE)
        yield SSEFormatter.format(done_response)
        logger.info(f"✅ HITL resume 완료: thread={resume_request.thread_id}")

    except Exception as e:
        logger.error(f"❌ HITL resume 에러: {e}")
        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e),
        )
        yield SSEFormatter.format(error_response)
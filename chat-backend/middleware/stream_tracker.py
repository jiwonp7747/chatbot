"""스트리밍 세션 추적 미들웨어"""
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import logging

logger = logging.getLogger("dev")

# 전역 상태 저장소: {stream_id: stream_data}
active_streams: Dict[str, dict] = {}


class StreamTrackerMiddleware(BaseHTTPMiddleware):
    """스트리밍 요청 추적 및 cleanup 보장 미들웨어"""

    async def dispatch(self, request: Request, call_next):
        # 스트리밍 요청에만 적용 (기존 + LangGraph 엔드포인트)
        if request.url.path in ["/chat/stream-chat", "/chat/stream-chat-graph", "/chat/resume"]:
            stream_id = str(uuid.uuid4())
            request.state.stream_id = stream_id

            logger.info(f"🎬 스트림 시작: {stream_id}")

            response = await call_next(request)

            # ✅ StreamingResponse의 body iterator를 감싸서 cleanup 보장
            original_body = response.body_iterator

            async def wrapped_body():
                try:
                    async for chunk in original_body:
                        yield chunk
                finally:
                    # Body iterator가 끝나거나 중단되면 cleanup 실행
                    logger.info(f"🎭 Response body 종료, cleanup 시작: {stream_id}")
                    await self._cleanup_stream(stream_id)

            response.body_iterator = wrapped_body()
            return response
        else:
            return await call_next(request)

    async def _cleanup_stream(self, stream_id: str):
        """스트림 종료 시 cleanup 처리"""
        if stream_id in active_streams:
            stream_data = active_streams[stream_id]
            content_length = len(stream_data.get('collected_content', ''))
            logger.info(f"🧹 Cleanup 시작: {stream_id}, content length: {content_length}")

            # DB 저장 콜백 실행
            if save_callback := stream_data.get("save_callback"):
                try:
                    await save_callback()
                    logger.info(f"✅ Cleanup 저장 완료: {stream_id}")
                except Exception as e:
                    logger.error(f"❌ Cleanup 저장 실패: {stream_id}, {e}")

            # 메모리에서 제거
            del active_streams[stream_id]
            logger.info(f"🗑️ 스트림 제거: {stream_id}")
        else:
            logger.warning(f"⚠️ 스트림 없음: {stream_id}")


def register_stream(stream_id: str, save_callback: Callable):
    """스트림 등록"""
    active_streams[stream_id] = {
        "created_at": datetime.utcnow(),
        "collected_content": "",
        "user_chat_created_at": None,
        "save_callback": save_callback
    }
    logger.info(f"📝 스트림 등록: {stream_id}")


def update_stream_content(stream_id: str, content: str):
    """스트림 content 업데이트"""
    if stream_id in active_streams:
        active_streams[stream_id]["collected_content"] += content


def set_user_chat_time(stream_id: str, created_at: datetime):
    """사용자 메시지 생성 시간 설정"""
    if stream_id in active_streams:
        active_streams[stream_id]["user_chat_created_at"] = created_at


def get_stream_data(stream_id: str) -> Optional[dict]:
    """스트림 데이터 조회"""
    return active_streams.get(stream_id)
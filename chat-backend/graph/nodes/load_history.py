"""
노드 1: 대화 기록 로드

DB에서 대화 세션의 이전 대화 기록을 불러옵니다.
"""
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import asc

from db.models import ChatMessage
from graph.schema.graph_state import ChatGraphState

logger = logging.getLogger("chat-server")


async def load_chat_history_node(
    state: ChatGraphState,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    대화 기록을 DB에서 로드하는 노드

    Args:
        state: LangGraph 상태
        db: 데이터베이스 세션

    Returns:
        업데이트된 상태 (message_history 포함)
    """
    chat_session_id = state.get("chat_session_id")
    message_history = []

    if chat_session_id:
        try:
            # 최근 10개의 메시지 조회
            query = (
                select(ChatMessage)
                .where(ChatMessage.chat_session_id == chat_session_id)
                .order_by(asc(ChatMessage.created_at))
                .limit(10)
            )
            result = await db.execute(query)
            messages = result.scalars().all()

            # 메시지를 dict 형태로 변환
            message_history = [
                {
                    "role": msg.role,
                    "content": msg.content,
                }
                for msg in messages
            ]

            logger.info(f"✅ 대화 기록 {len(message_history)}개 로드 완료")

        except Exception as e:
            logger.error(f"❌ 대화 기록 로드 실패: {e}")
            return {
                "message_history": [],
                "error": f"Failed to load chat history: {str(e)}"
            }
    else:
        logger.info("ℹ️ 새로운 채팅 세션 (대화 기록 없음)")

    return {
        "message_history": message_history
    }

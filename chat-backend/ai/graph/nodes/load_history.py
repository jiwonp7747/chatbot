"""
노드 1: 대화 기록 로드

DB에서 대화 세션의 이전 대화 기록을 불러와 LangChain 메시지 객체로 변환합니다.
"""
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import asc

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from db.models import ChatMessage
from ai.graph.schema.graph_state import ChatGraphState

logger = logging.getLogger("chat-server")


def _db_record_to_message(msg: ChatMessage):
    """DB 레코드를 LangChain 메시지 객체로 변환"""
    role = msg.role
    content = msg.content or ""
    msg_id = str(msg.chat_message_id)

    if role == "user":
        return HumanMessage(content=content, id=msg_id)
    elif role in ("assistant", "system"):  # system = 레거시 호환
        return AIMessage(content=content, id=msg_id)
    elif role == "tool":
        return ToolMessage(
            content=content,
            tool_call_id=msg.tool_call_id or "",
            name=msg.tool_name or "unknown",
            id=msg_id,
        )
    return HumanMessage(content=content, id=msg_id)  # fallback


async def load_chat_history_node(
    chat_session_id: int | None,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    대화 기록을 DB에서 로드하여 LangChain 메시지 객체로 반환하는 노드

    Args:
        chat_session_id: 채팅 세션 ID (runtime config에서 전달)
        db: 데이터베이스 세션

    Returns:
        업데이트된 상태 (messages: LangChain 메시지 객체 리스트)
    """
    messages = []

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
            db_messages = result.scalars().all()

            # DB 레코드를 LangChain 메시지 객체로 변환
            messages = [_db_record_to_message(msg) for msg in db_messages]

            logger.info(f"✅ 대화 기록 {len(messages)}개 로드 완료 (LangChain 메시지 객체)")

        except Exception as e:
            logger.error(f"❌ 대화 기록 로드 실패: {e}")
            return {
                "messages": [],
                "error": f"Failed to load chat history: {str(e)}"
            }
    else:
        logger.info("ℹ️ 새로운 채팅 세션 (대화 기록 없음)")

    return {
        "messages": messages
    }

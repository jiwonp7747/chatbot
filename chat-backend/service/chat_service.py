import os
import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from client.llm_adapter import get_llm_adapter
from common.exception.api_exception import ApiException
from common.response.code import FailureCode
from db.models import ChatSession, ModelType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc, text

logger = logging.getLogger("chat-server")

async def create_chat_title(user_prompt: str) -> Optional[str]:
    """사용자 프롬프트로 채팅 세션 제목 생성 (LLM 호출)"""
    class ChatTitleResponse(BaseModel):
        title: str
    try:
        llm_adapter = get_llm_adapter(provider="OPENAI")
        model = os.getenv("CHAT_TITLE_MODEL", "gpt-4.1-nano")

        completion = await llm_adapter.parse_completion(
            model=model,
            messages=[
                {"role": "system", "content": "사용자의 질문을 바탕으로 이 채팅 세션의 주제를 15자 이내로 요약해서 제목을 지어주세요."},
                {"role": "user", "content": user_prompt}
            ],
            response_model=ChatTitleResponse,
        )
        return completion.choices[0].message.parsed.title
    except Exception as e:
        logger.error(f"❌ 제목 생성 실패: {e}")
        return (user_prompt or "새 채팅")[:15]


async def create_or_get_session(
    thread_id: str,
    prompt: str,
) -> str:
    """세션 확인/생성 후 thread_id 반환. 새 세션이면 LLM으로 제목 생성."""
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            session_query = select(ChatSession).where(
                ChatSession.thread_id == thread_id
            )
            session_result = await db.execute(session_query)
            chat_session = session_result.scalar_one_or_none()

            if chat_session:
                return chat_session.thread_id

            # 새 세션: 프론트에서 전달받은 thread_id 사용 + LLM으로 제목 생성
            title = await create_chat_title(prompt)
            new_session = ChatSession(
                thread_id=thread_id,
                session_title=title or prompt[:15] or "새 채팅",
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            logger.info(f"✅ 새 세션 생성: thread={thread_id}")
            return thread_id
        except Exception as e:
            logger.error(f"❌ 세션 생성/조회 실패: {e}")
            await db.rollback()
            raise


async def get_chat_sessions(
        db: AsyncSession,
):
    # 최신순으로 정렬해서 가져오기
    query = select(ChatSession).order_by(desc(ChatSession.created_at))
    result = await db.execute(query)
    return result.scalars().all()

async def get_chat_messages(
        thread_id: str,
        db: AsyncSession,
):
    """checkpoint에서 메시지를 추출하여 반환"""
    # 1. session 존재 확인
    session_query = select(ChatSession).where(
        ChatSession.thread_id == thread_id
    )
    session_result = await db.execute(session_query)
    chat_session = session_result.scalar_one_or_none()

    if not chat_session:
        return []

    # 2. checkpointer에서 최신 checkpoint 가져오기
    from ai.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
    if not checkpointer:
        logger.warning("checkpointer가 초기화되지 않음")
        return []

    try:
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if not checkpoint_tuple:
            return []

        # 3. checkpoint에서 messages 채널 추출
        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])

        # 4. HumanMessage/AIMessage/ToolMessage만 필터링하여 프론트 포맷으로 변환
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
        result = []
        for idx, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                result.append({
                    "id": str(idx),
                    "role": "user",
                    "content": content,
                    "created_at": None,
                })
            elif isinstance(msg, AIMessage) and msg.content:
                content = msg.content if isinstance(msg.content, str) else ""
                if isinstance(msg.content, list):
                    parts = []
                    for part in msg.content:
                        if isinstance(part, str):
                            parts.append(part)
                        elif isinstance(part, dict) and part.get("type") == "text":
                            parts.append(part.get("text", ""))
                    content = "".join(parts)
                if content:  # 빈 content (tool_calls만 있는 AIMessage) 필터링
                    result.append({
                        "id": str(idx),
                        "role": "assistant",
                        "content": content,
                        "created_at": None,
                    })
            elif isinstance(msg, ToolMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                additional_kwargs = msg.additional_kwargs or {}
                result.append({
                    "id": str(idx),
                    "role": "tool",
                    "content": content,
                    "created_at": None,
                    "tool_name": getattr(msg, "name", None),
                    "tool_call_id": getattr(msg, "tool_call_id", None),
                    "data_ref_type": additional_kwargs.get("data_ref_type"),
                })

        logger.info(f"✅ checkpoint에서 메시지 {len(result)}개 추출: thread={thread_id}")
        return result
    except Exception as e:
        logger.error(f"❌ checkpoint 메시지 추출 실패: {e}")
        return []



async def get_tool_result(
        thread_id: str,
        tool_call_id: str,
):
    """체크포인트에서 특정 ToolMessage의 상세 데이터를 반환"""
    from ai.checkpointer import get_checkpointer
    from langchain_core.messages import ToolMessage

    checkpointer = get_checkpointer()
    if not checkpointer:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "checkpointer가 초기화되지 않음")

    config = {"configurable": {"thread_id": thread_id}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)
    if not checkpoint_tuple:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "체크포인트를 찾을 수 없습니다")

    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
    messages = channel_values.get("messages", [])

    # tool_call_id로 해당 ToolMessage 찾기
    target_msg = None
    for msg in messages:
        if isinstance(msg, ToolMessage) and getattr(msg, "tool_call_id", None) == tool_call_id:
            target_msg = msg
            break

    if not target_msg:
        raise ApiException(FailureCode.NOT_FOUND_DATA, f"tool_call_id={tool_call_id}에 해당하는 ToolMessage를 찾을 수 없습니다")

    additional_kwargs = target_msg.additional_kwargs or {}
    data_ref_type = additional_kwargs.get("data_ref_type")

    if data_ref_type == "artifact":
        # 체크포인트에 저장된 artifact 반환
        return {
            "tool_call_id": tool_call_id,
            "tool_name": getattr(target_msg, "name", None),
            "data_ref_type": "artifact",
            "data": target_msg.artifact,
        }
    elif data_ref_type == "file":
        # DatabaseBackend(PostgreSQL large_data 테이블)에서 읽기
        file_path = additional_kwargs.get("file_path")
        if not file_path:
            raise ApiException(FailureCode.NOT_FOUND_DATA, "파일 경로가 없습니다")

        from ai.backend.file_system_backend import get_database_backend
        backend = get_database_backend()
        file_content = await backend.aread(file_path, offset=0, limit=100000)

        if file_content.startswith("Error: file not found"):
            raise ApiException(FailureCode.NOT_FOUND_DATA, f"파일을 찾을 수 없습니다: {file_path}")

        return {
            "tool_call_id": tool_call_id,
            "tool_name": getattr(target_msg, "name", None),
            "data_ref_type": "file",
            "data": file_content,
        }
    else:
        # data_ref_type이 없는 경우, content 자체를 반환
        return {
            "tool_call_id": tool_call_id,
            "tool_name": getattr(target_msg, "name", None),
            "data_ref_type": None,
            "data": target_msg.content,
        }


async def get_available_model_list(
        db: AsyncSession,
):
    model_query = select(ModelType).where(ModelType.is_active.is_(True)).order_by(asc(ModelType.model_id))
    result = await db.execute(model_query)
    return result.scalars().all()


async def delete_chat_session(
        thread_id: str,
        db: AsyncSession,
):
    session_query = select(ChatSession).where(ChatSession.thread_id == thread_id)
    session_result = await db.execute(session_query)
    chat_session = session_result.scalar_one_or_none()

    if not chat_session:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "존재하지 않는 채팅 세션입니다")

    # checkpoint 테이블 정리
    await db.execute(text("DELETE FROM checkpoint_writes WHERE thread_id = :tid"), {"tid": thread_id})
    await db.execute(text("DELETE FROM checkpoint_blobs WHERE thread_id = :tid"), {"tid": thread_id})
    await db.execute(text("DELETE FROM checkpoints WHERE thread_id = :tid"), {"tid": thread_id})
    logger.info(f"🗑️ checkpoint 정리 완료: thread={thread_id}")

    await db.delete(chat_session)
    await db.commit()


async def update_chat_session_title(
        thread_id: str,
        session_title: str,
        db: AsyncSession,
):
    normalized_title = (session_title or "").strip()
    if not normalized_title:
        raise ApiException(FailureCode.BAD_REQUEST, "세션 제목은 비어있을 수 없습니다")

    session_query = select(ChatSession).where(ChatSession.thread_id == thread_id)
    session_result = await db.execute(session_query)
    chat_session = session_result.scalar_one_or_none()

    if not chat_session:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "존재하지 않는 채팅 세션입니다")

    chat_session.session_title = normalized_title
    chat_session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(chat_session)

    return chat_session

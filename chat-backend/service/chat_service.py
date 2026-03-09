import os
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from pydantic import BaseModel
from starlette.requests import Request

from client.llm_adapter import get_llm_adapter
from common.exception.api_exception import ApiException
from common.response.code import FailureCode
from config.prompt import SYSTEM_PROMPT
from db.models import ChatSession, ChatMessage, ModelType
from ai.graph.schema.stream import ChatRequest, ChatResponse, StreamStatus
from util.sse_formatter import SSEFormatter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc
from service.model_resolver import resolve_model_config

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


async def save_user_message_to_db(
    chat_session_id: int,
    prompt: str,
    created_at: datetime,
):
    if not chat_session_id or not prompt:
        raise ApiException(FailureCode.INTERNAL_SERVER_ERROR, "user chat saving content is null")

    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            # 세션 확인/생성
            session_query = select(ChatSession).where(
                ChatSession.chat_session_id == chat_session_id
            )
            session_result = await db.execute(session_query)
            chat_session = session_result.scalar_one_or_none()

            if not chat_session:
                # 새 세션: LLM으로 제목 생성
                title = await create_chat_title(prompt)
                new_session = ChatSession(
                    chat_session_id=chat_session_id,
                    session_title=title or prompt[:15] or "새 채팅"
                )
                db.add(new_session)
                await db.commit()
                await db.refresh(new_session)
                chat_session = new_session

            # 사용자 메시지 저장
            user_message = ChatMessage(
                role="user",
                content=prompt,
                chat_session_id=chat_session.chat_session_id,
                created_at=created_at,
            )
            db.add(user_message)
            await db.commit()
            logger.info(f"✅ 사용자 메시지 저장 완료: session={chat_session_id}")
        except Exception as e:
            logger.error(f"❌ 사용자 메시지 저장 실패: {e}")
            await db.rollback()


async def save_ai_message_to_db(
    chat_session_id: int,
    content: str,
):
    if not chat_session_id or not content:
        raise ApiException(FailureCode.INTERNAL_SERVER_ERROR, "ai chat saving content is null")

    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            session_query = select(ChatSession).where(
                ChatSession.chat_session_id == chat_session_id
            )
            session_result = await db.execute(session_query)
            chat_session = session_result.scalar_one_or_none()

            if not chat_session:
                raise ApiException(FailureCode.INTERNAL_SERVER_ERROR, f"세션을 찾을 수 없음: {chat_session_id}")

            ai_message = ChatMessage(
                role="assistant",
                content=content,
                chat_session_id=chat_session.chat_session_id,
                created_at=datetime.utcnow(),
            )
            db.add(ai_message)
            chat_session.updated_at = datetime.utcnow()
            await db.commit()
            logger.info(f"✅ AI 메시지 저장 완료: session={chat_session_id}")
        except Exception as e:
            logger.error(f"❌ AI 메시지 저장 실패: {e}")
            await db.rollback()


# streaming chat service
async def process_chat_request(
        request: ChatRequest,
        db: AsyncSession,
        http_request: Request,
)->AsyncGenerator[str, None]:
    message_history = None
    stream_id = str(uuid.uuid4())

    user_chat_created_at = datetime.utcnow()
    stream = None

    # 사용자 메시지 즉시 저장
    await save_user_message_to_db(request.chat_session_id, request.prompt, user_chat_created_at)

    try:
        query = select(ChatMessage).where(ChatMessage.chat_session_id == request.chat_session_id).order_by(asc(ChatMessage.created_at)).limit(10)
        result = await db.execute(query)
        messages = result.scalars().all()

        message_history = messages


    except Exception as e:
        logger.error(f"채팅 기록 조회 에러, {e}")

        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)



    try:
        messages = []
        messages.append(
            {"role": "system", "content": SYSTEM_PROMPT}
        )
        for chat_message in message_history:
            message = {
                "role": chat_message.role,
                "content": chat_message.content,
            }
            messages.append(message)
        messages.append(
            {"role": "user", "content": request.prompt}
        )

        # OpenAI API 호출 (stream=True)
        resolved_model = await resolve_model_config(db, request.model)
        llm_adapter = get_llm_adapter(
            model=resolved_model.api_model,
            provider=resolved_model.provider,
        )
        stream = await llm_adapter.stream_completion(
            model=resolved_model.api_model,
            messages=messages,
        )

        # 응답을 청크 단위로 스트리밍
        collected_content = ""
        async for chunk in stream:
            if await http_request.is_disconnected():
                logger.info(f"🔌 클라이언트 연결 끊김 감지: {stream_id}")
                await stream.aclose()
                # 중단 시에도 수집된 내용 저장
                if collected_content:
                    await save_ai_message_to_db(request.chat_session_id, collected_content)
                return

            content = chunk.choices[0].delta.content

            if content:
                collected_content += content
                response = ChatResponse(
                    content=content,
                    status=StreamStatus.STREAMING
                )
                yield SSEFormatter.format(response)

        # 정상 완료 - AI 응답 저장
        if collected_content:
            await save_ai_message_to_db(request.chat_session_id, collected_content)

        logger.info(f"✅ 스트리밍 정상 완료: {stream_id}")
        done_response = ChatResponse(content="", status=StreamStatus.DONE)
        yield SSEFormatter.format(done_response)

    except Exception as e:
        logger.error(f"❌ 스트리밍 에러: {stream_id}, {e}")
        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)


async def get_chat_sessions(
        db: AsyncSession,
):
    # 최신순으로 정렬해서 가져오기
    query = select(ChatSession).order_by(desc(ChatSession.created_at))
    result = await db.execute(query)
    return result.scalars().all()

async def get_chat_messages(
        chat_session_id: int,
        db: AsyncSession,
):
    query = select(ChatMessage).where(ChatMessage.chat_session_id == chat_session_id).order_by(asc(ChatMessage.created_at))
    result = await db.execute(query)
    return result.scalars().all()



async def get_available_model_list(
        db: AsyncSession,
):
    model_query = select(ModelType).where(ModelType.is_active.is_(True)).order_by(asc(ModelType.model_id))
    result = await db.execute(model_query)
    return result.scalars().all()


async def delete_chat_session(
        chat_session_id: int,
        db: AsyncSession,
):
    session_query = select(ChatSession).where(ChatSession.chat_session_id == chat_session_id)
    session_result = await db.execute(session_query)
    chat_session = session_result.scalar_one_or_none()

    if not chat_session:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "존재하지 않는 채팅 세션입니다")

    await db.delete(chat_session)
    await db.commit()


async def update_chat_session_title(
        chat_session_id: int,
        session_title: str,
        db: AsyncSession,
):
    normalized_title = (session_title or "").strip()
    if not normalized_title:
        raise ApiException(FailureCode.BAD_REQUEST, "세션 제목은 비어있을 수 없습니다")

    session_query = select(ChatSession).where(ChatSession.chat_session_id == chat_session_id)
    session_result = await db.execute(session_query)
    chat_session = session_result.scalar_one_or_none()

    if not chat_session:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "존재하지 않는 채팅 세션입니다")

    chat_session.session_title = normalized_title
    chat_session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(chat_session)

    return chat_session

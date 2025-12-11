import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from pydantic import BaseModel
from starlette.requests import Request

from client.openai_client import aclient
from common.exception.api_exception import ApiException
from common.response.code import FailureCode
from db.chat_models import ChatSession, ChatMessage
from db.database import get_db
from schema import ChatRequest, ChatResponse, StreamStatus
from sse.sse_util import SSEFormatter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc
from middleware.stream_tracker import (
    register_stream,
    update_stream_content,
    set_user_chat_time,
    get_stream_data
)

logger = logging.getLogger("chat-server")


# 💾 DB 저장 로직 분리
async def save_chat_to_db(
        request: ChatRequest,
        collected_content: str,
        user_chat_created_at: datetime,
        db: AsyncSession
):
    if not request.chat_session_id:
        raise ApiException(FailureCode.BAD_REQUEST, "non chat session value")

    if not collected_content or not request.prompt:
        logger.info("no data to save db")
        return

    logger.info(f"💾 DB 저장 시작 (content length: {len(collected_content)})")
    ai_chat_created_at = datetime.utcnow()

    try:
        # 세션 처리
        session_query = select(ChatSession).where(
            ChatSession.chat_session_id == request.chat_session_id
        )
        session_result = await db.execute(session_query)
        chat_session = session_result.scalar_one_or_none()

        if not chat_session:
            title = await create_chat_title(
                user_prompt=request.prompt,
                ai_response=collected_content
            )

            new_session = ChatSession(
                chat_session_id=request.chat_session_id,
                session_title=title or "새 채팅"
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            chat_session = new_session

        if chat_session:
            # 메시지 저장
            user_message = ChatMessage(
                role="user",
                content=request.prompt,
                chat_session_id=chat_session.chat_session_id,
                created_at=user_chat_created_at,
            )

            ai_message = ChatMessage(
                role="system",
                content=collected_content,
                chat_session_id=chat_session.chat_session_id,
                created_at=ai_chat_created_at,
            )

            chat_session.updated_at = datetime.utcnow()

            db.add(user_message)
            db.add(ai_message)
            await db.commit()

            logger.info(f"✅ 메시지 저장 완료")
        else:
            logger.warning("⚠️ 세션을 찾을 수 없음")

    except Exception as db_error:
        logger.error(f"❌ DB 저장 실패: {db_error}")
        await db.rollback()


# streaming chat service
async def process_chat_request(
        request: ChatRequest,
        db: AsyncSession,
        http_request: Request,
)->AsyncGenerator[str, None]:
    message_history = None
    # 🎫 Middleware가 설정한 stream_id 가져오기
    stream_id = getattr(http_request.state, 'stream_id', None)
    if not stream_id:
        logger.error("❌ stream_id가 없습니다!")
        raise RuntimeError("stream_id not found in request.state")

    user_chat_created_at = datetime.utcnow()
    stream = None

    # 💾 DB 저장 콜백 함수 정의
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

            # ✅ 새로운 독립적인 DB 세션 생성
            async for new_db in get_db():
                try:
                    await save_chat_to_db(request, collected_content, user_time, new_db)
                except Exception as e:
                    logger.error(f"❌ Callback DB 저장 실패: {stream_id}, {e}")
                finally:
                    await new_db.close()
                break  # async generator는 한 번만 실행
        else:
            logger.info(f"ℹ️ 저장할 content 없음: {stream_id}")

    # 📝 스트림 등록
    register_stream(stream_id, save_callback)
    set_user_chat_time(stream_id, user_chat_created_at)

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
            {"role": "system", "content": "당신은 도움이 되는 AI 어시스턴트입니다."}
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
        stream = await aclient.chat.completions.create(
            model=request.model,
            messages=messages,
            stream=True
        )

        # 응답을 청크 단위로 스트리밍
        async for chunk in stream:
            # 🔍 연결 끊김 감지
            if await http_request.is_disconnected():
                logger.info(f"🔌 클라이언트 연결 끊김 감지: {stream_id}")
                # ⚡ OpenAI 스트림 즉시 중단 (토큰 비용 절감)
                await stream.aclose()
                logger.info(f"⚡ OpenAI 스트림 중단됨: {stream_id}")
                # 💾 DB 저장은 Middleware cleanup이 처리함
                return  # generator 종료

            # 델타(변화량) 추출
            content = chunk.choices[0].delta.content

            if content:
                # 📊 전역 상태 업데이트
                update_stream_content(stream_id, content)

                # SSEFormatter 사용
                response = ChatResponse(
                    content=content,
                    status=StreamStatus.STREAMING
                )
                yield SSEFormatter.format(response)

        # 🔄 스트리밍 정상 완료
        logger.info(f"✅ 스트리밍 정상 완료: {stream_id}")

        # DONE 상태 전송
        done_response = ChatResponse(
            content="",
            status=StreamStatus.DONE
        )
        yield SSEFormatter.format(done_response)

        # 💾 DB 저장은 Middleware cleanup이 처리함

    except Exception as e:
        logger.error(f"❌ 스트리밍 에러: {stream_id}, {e}")

        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)

        # 💾 DB 저장은 Middleware cleanup이 처리함 (에러 시에도)


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


async def create_chat_title(
        user_prompt: str,
        ai_response: str
)->Optional[str]:
    class ChatTitleResponse(BaseModel):
        title: str
    try:
        # 1. 제목 생성을 위한 별도의 LLM 호출 (가벼운 모델 사용 권장: gpt-4o-mini 등)
        completion = await aclient.beta.chat.completions.parse(
            model="gpt-4.1-nano",  # 싸고 빠른 모델 추천
            messages=[
                {"role": "system", "content": "사용자의 질문과 AI의 답변을 바탕으로 이 채팅 세션의 주제를 15자 이내로 요약해서 제목을 지어주세요."},
                {"role": "user", "content": f"질문: {user_prompt}\n\n답변: {ai_response}"}
            ],
            response_format=ChatTitleResponse
        )

        return completion.choices[0].message.parsed.title

    except Exception as e:
        print(f"❌ 제목 생성 실패: {e}")
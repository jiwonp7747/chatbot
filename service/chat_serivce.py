import json
from datetime import datetime
from typing import AsyncGenerator, Optional

from pydantic import BaseModel
from starlette.requests import Request

from client.openai_client import aclient
from db.chat_models import ChatSession, ChatMessage
from schema import ChatRequest, ChatResponse, StreamStatus
from sse.sse_util import SSEFormatter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, asc


# streaming chat service
async def process_chat_request(
        request: ChatRequest,
        db: AsyncSession,
        http_request: Request,  # 연결 끊김 감지용
)->AsyncGenerator[str, None]:
    user_chat_created_at = datetime.utcnow()
    collected_content = ""
    is_disconnected = False
    stream = None

    try:
        # OpenAI API 호출 (stream=True)
        stream = await aclient.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": "당신은 도움이 되는 AI 어시스턴트입니다."},
                {"role": "user", "content": request.prompt}
            ],
            stream=True
        )

        # 응답을 청크 단위로 스트리밍
        async for chunk in stream:
            # 🔍 연결 끊김 감지
            if await http_request.is_disconnected():
                is_disconnected = True
                # ⚡ OpenAI 스트림 즉시 중단 (토큰 비용 절감)
                await stream.aclose()
                break

            # 델타(변화량) 추출
            content = chunk.choices[0].delta.content

            if content:
                collected_content += content
                # SSEFormatter 사용
                response = ChatResponse(
                    content=content,
                    status=StreamStatus.STREAMING
                )
                yield SSEFormatter.format(response)

        # 🔄 스트리밍 정상 완료 시 DONE 상태 전송
        if not is_disconnected:
            done_response = ChatResponse(
                content="",
                status=StreamStatus.DONE
            )
            yield SSEFormatter.format(done_response)

    except Exception as e:
        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)

    finally:
        # 💾 DB 저장 (정상 완료, 연결 끊김, 에러 모두 저장)
        # collected_content가 있으면 저장 (부분 응답도 저장)
        if collected_content and request.prompt:
            ai_chat_created_at = datetime.utcnow()

            try:
                # 세션 처리
                chat_session = None
                if not request.chat_session_id:
                    # 첫 메시지 → 새 세션 생성
                    title = await create_chat_title(
                        user_prompt=request.prompt,
                        ai_response=collected_content
                    )

                    new_session = ChatSession(
                        session_title=title or "새 채팅"
                    )
                    db.add(new_session)
                    await db.commit()
                    await db.refresh(new_session)
                    chat_session = new_session
                else:
                    # 기존 세션 조회
                    session_query = select(ChatSession).where(
                        ChatSession.chat_session_id == request.chat_session_id
                    )
                    session_result = await db.execute(session_query)
                    chat_session = session_result.scalar_one_or_none()

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

            except Exception as db_error:
                # DB 저장 실패는 로깅만 (클라이언트는 이미 연결 끊김 가능)
                print(f"❌ DB 저장 실패: {db_error}")
                await db.rollback()


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
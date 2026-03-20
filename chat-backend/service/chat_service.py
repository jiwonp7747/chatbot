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
        checkpoint_id: Optional[str] = None,
):
    """checkpoint에서 메시지를 추출하여 반환. checkpoint_id 지정 시 해당 시점의 메시지를 반환."""
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
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
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
            logger.info(f"[메시지 디버그] idx={idx}, type={type(msg).__name__}, is_ToolMessage={isinstance(msg, ToolMessage)}, is_dict={isinstance(msg, dict)}")
            if isinstance(msg, dict):
                logger.info(f"[메시지 디버그] dict 키: {list(msg.keys())}")
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
                response_metadata = msg.response_metadata or {}
                logger.info(
                    f"[ToolMessage 읽기] name={getattr(msg, 'name', None)}, "
                    f"tool_call_id={getattr(msg, 'tool_call_id', None)}, "
                    f"response_metadata={response_metadata}, "
                    f"additional_kwargs={msg.additional_kwargs}"
                )
                result.append({
                    "id": str(idx),
                    "role": "tool",
                    "content": content,
                    "created_at": None,
                    "tool_name": getattr(msg, "name", None),
                    "tool_call_id": getattr(msg, "tool_call_id", None),
                    "data_ref_type": response_metadata.get("data_ref_type"),
                })

        # 5. 서브에이전트 메시지 연결
        # AIMessage의 tool_calls에서 subagent_type 매핑 수집
        tool_call_subagent_map: dict[str, str] = {}  # tool_call_id → subagent_type
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
                for tc in msg.tool_calls:
                    if tc.get("name") == "task":
                        subagent_type = tc.get("args", {}).get("subagent_type")
                        if subagent_type:
                            tool_call_subagent_map[tc["id"]] = subagent_type

        # 서브에이전트 메시지 조회 및 연결
        if tool_call_subagent_map:
            from db.checkpoint_models import CheckPoint
            from db.database import AsyncSessionLocal

            # checkpoint_ns별 lc_agent_name 조회
            async with AsyncSessionLocal() as ns_db:
                ns_query = (
                    select(CheckPoint.checkpoint_ns, CheckPoint.metadata_)
                    .where(
                        CheckPoint.thread_id == thread_id,
                        CheckPoint.checkpoint_ns != "",
                    )
                    .distinct(CheckPoint.checkpoint_ns)
                )
                ns_result = await ns_db.execute(ns_query)
                ns_rows = ns_result.all()

            # agent_name → checkpoint_ns 맵
            agent_ns_map: dict[str, str] = {}
            for row in ns_rows:
                meta = row.metadata_ or {}
                agent_name = meta.get("lc_agent_name")
                if agent_name:
                    agent_ns_map[agent_name] = row.checkpoint_ns

            # ToolMessage(name="task")에 서브에이전트 메시지 연결
            for item in result:
                if item.get("role") == "tool" and item.get("tool_name") == "task":
                    tc_id = item.get("tool_call_id")
                    subagent_type = tool_call_subagent_map.get(tc_id)
                    if subagent_type and subagent_type in agent_ns_map:
                        cp_ns = agent_ns_map[subagent_type]
                        try:
                            # 서브그래프의 head checkpoint에서 메시지 추출
                            sub_config = {"configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": cp_ns,
                            }}
                            sub_tuple = await checkpointer.aget_tuple(sub_config)
                            if sub_tuple:
                                sub_channel = sub_tuple.checkpoint.get("channel_values", {})
                                sub_msgs = sub_channel.get("messages", [])
                                sub_result = []
                                for si, sm in enumerate(sub_msgs):
                                    if isinstance(sm, HumanMessage):
                                        sub_content = sm.content if isinstance(sm.content, str) else str(sm.content)
                                        sub_result.append({
                                            "id": f"sub-{si}",
                                            "role": "user",
                                            "content": sub_content,
                                        })
                                    elif isinstance(sm, AIMessage) and sm.content:
                                        sub_content = sm.content if isinstance(sm.content, str) else ""
                                        if isinstance(sm.content, list):
                                            parts = []
                                            for part in sm.content:
                                                if isinstance(part, str):
                                                    parts.append(part)
                                                elif isinstance(part, dict) and part.get("type") == "text":
                                                    parts.append(part.get("text", ""))
                                            sub_content = "".join(parts)
                                        if sub_content:
                                            sub_result.append({
                                                "id": f"sub-{si}",
                                                "role": "assistant",
                                                "content": sub_content,
                                            })
                                    elif isinstance(sm, ToolMessage):
                                        sub_content = sm.content if isinstance(sm.content, str) else str(sm.content)
                                        sub_result.append({
                                            "id": f"sub-{si}",
                                            "role": "tool",
                                            "content": sub_content[:200],  # 서브에이전트 도구 결과는 축약
                                            "tool_name": getattr(sm, "name", None),
                                        })
                                item["agent_name"] = subagent_type
                                item["sub_messages"] = sub_result
                                logger.info(f"✅ 서브에이전트 메시지 {len(sub_result)}개 연결: agent={subagent_type}")
                        except Exception as e:
                            logger.warning(f"서브에이전트 메시지 조회 실패: agent={subagent_type}, error={e}")

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

    response_metadata = target_msg.response_metadata or {}
    data_ref_type = response_metadata.get("data_ref_type")

    if data_ref_type == "artifact":
        # 체크포인트에 저장된 artifact 반환
        return {
            "tool_call_id": tool_call_id,
            "tool_name": getattr(target_msg, "name", None),
            "data_ref_type": "artifact",
            "data": target_msg.artifact,
        }
    else:
        # data_ref_type이 없거나 file인 경우, content 자체를 반환
        return {
            "tool_call_id": tool_call_id,
            "tool_name": getattr(target_msg, "name", None),
            "data_ref_type": data_ref_type,
            "data": target_msg.content,
        }


async def download_tool_file(
        thread_id: str,
        tool_call_id: str,
):
    """ToolMessage에 연결된 파일을 S3에서 읽어 (bytes, filename) 튜플 반환"""
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

    target_msg = None
    for msg in messages:
        if isinstance(msg, ToolMessage) and getattr(msg, "tool_call_id", None) == tool_call_id:
            target_msg = msg
            break

    if not target_msg:
        raise ApiException(FailureCode.NOT_FOUND_DATA, f"tool_call_id={tool_call_id}에 해당하는 ToolMessage를 찾을 수 없습니다")

    response_metadata = target_msg.response_metadata or {}
    data_ref_type = response_metadata.get("data_ref_type")

    if data_ref_type != "file":
        raise ApiException(FailureCode.BAD_REQUEST, "이 ToolMessage는 파일 타입이 아닙니다")

    file_path = response_metadata.get("file_path")
    if not file_path:
        raise ApiException(FailureCode.NOT_FOUND_DATA, "파일 경로가 없습니다")

    from ai.backend import get_s3_backend
    import json

    backend = get_s3_backend()

    # S3에서 raw JSON 데이터 읽기
    file_data = await backend._get_file_data(file_path)
    if not file_data:
        raise ApiException(FailureCode.NOT_FOUND_DATA, f"파일을 찾을 수 없습니다: {file_path}")

    # content는 라인 배열 → 줄바꿈으로 합쳐서 bytes 변환
    content_lines = file_data.get("content", [])
    content_str = "\n".join(content_lines)
    content_bytes = content_str.encode("utf-8")

    # 파일명 추출 (경로의 마지막 부분)
    import os as _os
    filename = _os.path.basename(file_path)

    return content_bytes, filename


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

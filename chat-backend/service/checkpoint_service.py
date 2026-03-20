import logging
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.checkpoint_models import CheckPoint

logger = logging.getLogger("checkpoint")


async def get_checkpoints_by_thread_id(
        thread_id: str,
        db: AsyncSession,
):
    query = (select(CheckPoint).where(CheckPoint.thread_id == thread_id)
             .order_by(desc(CheckPoint.checkpoint_id)))
    result = await db.execute(query)
    return result.scalars().all()


async def get_checkpoint_graph(
        thread_id: str,
        db: AsyncSession,
        checkpoint_ns: str | None = None,  # None = all, "" = main only
):
    """checkpoint 그래프 조회 — 트리 구조의 nodes 반환

    checkpoints 테이블의 metadata(step, source)만 사용하여 빠르게 조회.
    blob 역직렬화 없이 그래프 구조만 반환.
    """
    conditions = [CheckPoint.thread_id == thread_id]
    if checkpoint_ns is not None:
        conditions.append(CheckPoint.checkpoint_ns == checkpoint_ns)

    query = (
        select(CheckPoint)
        .where(*conditions)
        .order_by(CheckPoint.checkpoint_id)
    )

    result = await db.execute(query)
    checkpoints = result.scalars().all()

    if not checkpoints:
        return {"thread_id": thread_id, "nodes": []}

    # parent → children 맵 구성 (is_head 판별용)
    child_count: dict[str, int] = {}
    for cp in checkpoints:
        pid = cp.parent_checkpoint_id
        if pid:
            child_count[pid] = child_count.get(pid, 0) + 1

    # head = 자식이 없는 노드
    all_ids = {cp.checkpoint_id for cp in checkpoints}
    head_ids = all_ids - set(child_count.keys())

    nodes = []
    for cp in checkpoints:
        metadata = cp.metadata_ or {}
        nodes.append({
            "checkpoint_id": cp.checkpoint_id,
            "parent_checkpoint_id": cp.parent_checkpoint_id,
            "step": metadata.get("step"),
            "source": metadata.get("source"),
            "checkpoint_ns": cp.checkpoint_ns,
            "is_head": cp.checkpoint_id in head_ids,
            "agent_name": metadata.get("lc_agent_name"),
        })

    # Selective deserialization for input checkpoints (message preview)
    from ai.checkpointer import get_checkpointer

    input_cp_ids = [
        n["checkpoint_id"] for n in nodes
        if n["source"] == "input" and n["checkpoint_ns"] == ""
    ]

    input_previews: dict[str, str] = {}
    if input_cp_ids:
        checkpointer = get_checkpointer()
        if checkpointer:
            for cp_id in input_cp_ids:
                try:
                    config = {"configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": cp_id,
                        "checkpoint_ns": "",
                    }}
                    tup = await checkpointer.aget_tuple(config)
                    if tup:
                        msgs = tup.checkpoint.get("channel_values", {}).get("messages", [])
                        for msg in reversed(msgs):
                            if isinstance(msg, HumanMessage):
                                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                                input_previews[cp_id] = content[:80]
                                break
                except Exception as e:
                    logger.warning(f"input preview extraction failed: {e}")

    # Apply previews to nodes
    for node in nodes:
        if node["checkpoint_id"] in input_previews:
            node["summary"] = input_previews[node["checkpoint_id"]]
        else:
            node["summary"] = None

    return {
        "thread_id": thread_id,
        "nodes": nodes,
    }


async def get_checkpoint_messages(
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
):
    """특정 checkpoint 시점의 메시지를 역직렬화하여 반환

    checkpointer.aget_tuple()을 사용하여 blob에서 state를 복원하고
    messages 채널에서 HumanMessage/AIMessage를 추출.
    """
    from ai.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
    if not checkpointer:
        logger.warning("checkpointer가 초기화되지 않음")
        return []

    try:
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if not checkpoint_tuple:
            return []

        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])

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
                if content:
                    result.append({
                        "id": str(idx),
                        "role": "assistant",
                        "content": content,
                        "created_at": None,
                    })

        logger.info(f"checkpoint 메시지 {len(result)}개 추출: thread={thread_id}, checkpoint={checkpoint_id}")
        return result
    except Exception as e:
        logger.error(f"checkpoint 메시지 추출 실패: {e}")
        return []


async def get_checkpoint_debug(
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str = "",
):
    """특정 checkpoint의 전체 state를 디버깅용으로 반환

    channel_values 내 모든 채널을 직렬화하여 반환.
    messages 채널은 각 메시지의 타입, 모든 필드를 포함.
    """
    from ai.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
    if not checkpointer:
        return {"error": "checkpointer가 초기화되지 않음"}

    try:
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if not checkpoint_tuple:
            return {"error": "체크포인트를 찾을 수 없습니다"}

        checkpoint = checkpoint_tuple.checkpoint
        metadata = checkpoint_tuple.metadata
        channel_values = checkpoint.get("channel_values", {})

        # messages 채널 상세 직렬화
        messages_debug = []
        raw_messages = channel_values.get("messages", [])
        for idx, msg in enumerate(raw_messages):
            msg_info = {
                "idx": idx,
                "python_type": type(msg).__name__,
                "is_dict": isinstance(msg, dict),
            }

            if isinstance(msg, (HumanMessage, AIMessage, ToolMessage)):
                content = msg.content
                if isinstance(content, list):
                    # multipart content 처리
                    parts = []
                    for part in content:
                        if isinstance(part, str):
                            parts.append(part)
                        elif isinstance(part, dict) and part.get("type") == "text":
                            parts.append(part.get("text", ""))
                    content = "".join(parts)

                msg_info.update({
                    "role": "user" if isinstance(msg, HumanMessage) else "assistant" if isinstance(msg, AIMessage) else "tool",
                    "content": content if isinstance(content, str) else str(content),
                    "id": getattr(msg, "id", None),
                    "name": getattr(msg, "name", None),
                    "additional_kwargs": msg.additional_kwargs or {},
                    "response_metadata": msg.response_metadata or {},
                })

                if isinstance(msg, AIMessage):
                    msg_info["tool_calls"] = getattr(msg, "tool_calls", [])
                elif isinstance(msg, ToolMessage):
                    msg_info["tool_call_id"] = getattr(msg, "tool_call_id", None)
                    msg_info["has_artifact"] = msg.artifact is not None
                    if msg.artifact is not None:
                        artifact_str = str(msg.artifact)
                        msg_info["artifact_preview"] = artifact_str[:500] if len(artifact_str) > 500 else artifact_str
            elif isinstance(msg, dict):
                msg_info["keys"] = list(msg.keys())
                msg_info["data"] = {k: str(v)[:200] for k, v in msg.items()}
            else:
                msg_info["repr"] = repr(msg)[:500]

            messages_debug.append(msg_info)

        # 다른 채널들
        other_channels = {}
        for key, value in channel_values.items():
            if key == "messages":
                continue
            try:
                other_channels[key] = str(value)[:1000]
            except Exception:
                other_channels[key] = f"<직렬화 불가: {type(value).__name__}>"

        return {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "checkpoint_ns": checkpoint_ns,
            "metadata": metadata,
            "channel_keys": list(channel_values.keys()),
            "messages_count": len(raw_messages),
            "messages": messages_debug,
            "other_channels": other_channels,
        }
    except Exception as e:
        logger.error(f"checkpoint 디버그 조회 실패: {e}")
        return {"error": str(e)}

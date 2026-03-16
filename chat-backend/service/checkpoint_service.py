import logging
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage
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
        checkpoint_ns: str = "",
):
    """checkpoint 그래프 조회 — 트리 구조의 nodes 반환

    checkpoints 테이블의 metadata(step, source)만 사용하여 빠르게 조회.
    blob 역직렬화 없이 그래프 구조만 반환.
    """
    query = (
        select(CheckPoint)
        .where(
            CheckPoint.thread_id == thread_id,
            CheckPoint.checkpoint_ns == checkpoint_ns,
        )
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
        })

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

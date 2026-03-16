from fastapi import Depends, APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
import service.checkpoint_service as checkpoint_service
from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate

from db.database import get_db

router = APIRouter(prefix="/checkpoint", tags=["checkpoint"])

@router.get("")
async def get_checkpoints_by_thread_id(
    thread_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    checkpoints = await checkpoint_service.get_checkpoints_by_thread_id(thread_id, db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, checkpoints)

@router.get("/graph")
async def get_checkpoint_graph(
    thread_id: str = Query(...),
    checkpoint_ns: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """checkpoint 그래프 조회 — 트리 구조의 nodes 반환 (blob 역직렬화 없이 빠름)"""
    graph = await checkpoint_service.get_checkpoint_graph(thread_id, db, checkpoint_ns)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, graph)

@router.get("/messages")
async def get_checkpoint_messages(
    thread_id: str = Query(...),
    checkpoint_id: str = Query(...),
    checkpoint_ns: str = Query(default=""),
):
    """특정 checkpoint 시점의 메시지 상세 조회 (blob 역직렬화)"""
    messages = await checkpoint_service.get_checkpoint_messages(
        thread_id, checkpoint_id, checkpoint_ns,
    )
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, messages)

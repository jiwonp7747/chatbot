from fastapi import Depends, FastAPI, APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
import service.checkpoint_service as checkpoint_service
from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate

from db.database import get_db

router = APIRouter(prefix="/checkpoint", tags=["checkpoint"])

@router.get("")
async def get_checkpoints_by_thread_id(
    thread_id,
    db: AsyncSession = Depends(get_db),
):
    checkpoints = await checkpoint_service.get_checkpoints_by_thread_id(thread_id, db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, checkpoints)
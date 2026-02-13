from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate
from db.database import get_db
from schema.chat_session_schema import ChatSessionResponse, ChatSessionTitleUpdateRequest
import service.chat_service as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get(
    "/session",
    response_model=List[ChatSessionResponse],
)
async def read_sessions(
        db: AsyncSession = Depends(get_db)
):
    sessions = await chat_service.get_chat_sessions(db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, sessions)

@router.get(
    "/message/{chat_session_id}",
)
async def read_messages(
    chat_session_id: int,
    db: AsyncSession = Depends(get_db),
):
    messages = await chat_service.get_chat_messages(chat_session_id, db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, messages)

@router.get(
    "/model"
)
async def available_model_list(
        db: AsyncSession = Depends(get_db),
):
    model_types = await chat_service.get_available_model_list(db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, model_types)


@router.delete("/session/{chat_session_id}")
async def delete_session(
        chat_session_id: int,
        db: AsyncSession = Depends(get_db),
):
    await chat_service.delete_chat_session(chat_session_id, db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE)


@router.patch("/session/{chat_session_id}/title")
async def update_session_title(
        chat_session_id: int,
        request: ChatSessionTitleUpdateRequest,
        db: AsyncSession = Depends(get_db),
):
    updated_session = await chat_service.update_chat_session_title(
        chat_session_id=chat_session_id,
        session_title=request.session_title,
        db=db,
    )
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, updated_session)

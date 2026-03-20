from fastapi import Depends, APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import io

from common.response.code import SuccessCode
from common.response.response_template import ResponseTemplate
from db.database import get_db
from schema.chat_session_schema import ChatSessionResponse, ChatSessionTitleUpdateRequest, ToolResultResponse
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
    "/message/{thread_id}",
)
async def read_messages(
    thread_id: str,
    checkpoint_id: Optional[str] = Query(default=None, description="특정 체크포인트 시점의 메시지 조회"),
    db: AsyncSession = Depends(get_db),
):
    messages = await chat_service.get_chat_messages(thread_id, db, checkpoint_id=checkpoint_id)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, messages)

@router.get(
    "/tool-result/{thread_id}/{tool_call_id}",
)
async def read_tool_result(
    thread_id: str,
    tool_call_id: str,
):
    result = await chat_service.get_tool_result(thread_id, tool_call_id)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, result)

@router.get(
    "/tool-result/{thread_id}/{tool_call_id}/download",
)
async def download_tool_file(
    thread_id: str,
    tool_call_id: str,
):
    content_bytes, filename = await chat_service.download_tool_file(thread_id, tool_call_id)
    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get(
    "/model"
)
async def available_model_list(
        db: AsyncSession = Depends(get_db),
):
    model_types = await chat_service.get_available_model_list(db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, model_types)


@router.delete("/session/{thread_id}")
async def delete_session(
        thread_id: str,
        db: AsyncSession = Depends(get_db),
):
    await chat_service.delete_chat_session(thread_id, db)
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE)


@router.patch("/session/{thread_id}/title")
async def update_session_title(
        thread_id: str,
        request: ChatSessionTitleUpdateRequest,
        db: AsyncSession = Depends(get_db),
):
    updated_session = await chat_service.update_chat_session_title(
        thread_id=thread_id,
        session_title=request.session_title,
        db=db,
    )
    return ResponseTemplate.success(SuccessCode.SUCCESS_CODE, updated_session)

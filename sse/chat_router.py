from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from db.database import get_db
from schema import ChatRequest
from service import *

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/stream-chat")
async def stream_chat(
        chat_request: ChatRequest,
        http_request: Request,  # 연결 끊김 감지용
        db: AsyncSession=Depends(get_db),
):
    return StreamingResponse(
        process_chat_request(chat_request, db, http_request),
        media_type="text/event-stream"
    )
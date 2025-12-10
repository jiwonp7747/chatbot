from fastapi import APIRouter
from starlette.responses import StreamingResponse

from schema import ChatRequest
from service import *

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/stream-chat")
async def stream_chat(
        request: ChatRequest,
):
    return StreamingResponse(
        process_chat_request(request),
        media_type="text/event-stream"  # 핵심: MIME 타입 설정
    )
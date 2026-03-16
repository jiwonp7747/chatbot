from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from db.database import get_db
from ai.graph.schema.stream import ChatRequest, ResumeRequest, ToolSchemaRequest
from service.chat_langgraph_service import process_chat

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/stream-chat-graph")
async def stream_chat_graph(
        chat_request: ChatRequest,
        http_request: Request,  # 연결 끊김 감지용
        db: AsyncSession=Depends(get_db),
):
    """LangGraph 기반 채팅 엔드포인트 (신규)"""
    return StreamingResponse(
        process_chat(chat_request, db, http_request),
        media_type="text/event-stream"
    )

@router.post("/resume")
async def resume_chat(
        resume_request: ResumeRequest,
        http_request: Request,
        db: AsyncSession=Depends(get_db),
):
    """HITL 재개 엔드포인트 - 도구 실행 승인/거부/수정 후 그래프 재개"""
    return StreamingResponse(
        process_chat(resume_request, db, http_request),
        media_type="text/event-stream"
    )

@router.post("/tool-schemas")
async def get_tool_schemas_endpoint(
        request: ToolSchemaRequest,
):
    """도구별 JSON Schema 조회 — HITL 수정 폼 렌더링용"""
    from ai.graph.orchestrator import get_tool_schemas
    schemas = get_tool_schemas(request.tool_names)
    return {"success": True, "data": schemas}
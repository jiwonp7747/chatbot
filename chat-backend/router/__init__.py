from fastapi import APIRouter
from router.chat_router import router as chat_router
from router.chat_session_router import router as chat_session_router
from router.mcp_router import router as mcp_router
from router.rag_router import router as rag_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(chat_session_router)
router.include_router(mcp_router)
router.include_router(rag_router)

__all__ = ["router"]

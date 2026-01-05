from fastapi import APIRouter

from api.chat_session_router import router as chat_session_router
from api.echart_mcp_server_test_router import router as echart_mcp_server_test_router

router = APIRouter()

router.include_router(chat_session_router)
router.include_router(echart_mcp_server_test_router)

__all__ = ["router"]
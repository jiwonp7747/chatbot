from fastapi import APIRouter
from router.chat_router import router as chat_router
from router.chat_session_router import router as chat_session_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(chat_session_router)

__all__ = ["router"]

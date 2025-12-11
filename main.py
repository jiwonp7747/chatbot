import uvicorn
from fastapi import FastAPI
from core.config import middleware_config
from middleware.logging import LoggingMiddleware
from sse.chat_router import router as sse_router
from api.chat_session_router import router as chat_session_router
from common.exceptionhandler import register_exception_handler
from middleware.stream_tracker import StreamTrackerMiddleware
from core.config.logger import setup_logging

setup_logging()

app = FastAPI()

middleware_config.set_cors_config(app)

# 🔧 스트림 추적 미들웨어 등록
app.add_middleware(StreamTrackerMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(sse_router)
app.include_router(chat_session_router)
register_exception_handler(app)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
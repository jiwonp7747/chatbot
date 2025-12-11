import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text

from core.config import middleware_config
from core.config.prompt.prompt import load_system_prompts
from middleware.logging import LoggingMiddleware
from middleware.stream_tracker import StreamTrackerMiddleware
from sse.chat_router import router as sse_router
from api.chat_session_router import router as chat_session_router
from common.exceptionhandler import register_exception_handler
from core.config.logger import setup_logging
from db.database import AsyncSessionLocal, engine  # DB 엔진 및 세션


# --- [Lifespan] 서버 시작/종료 시 실행될 로직 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 서버 시작 프로세스 가동...")

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        print("✅ 데이터베이스 연결 성공")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        # DB 연결 실패 시 서버를 켜지 않으려면 여기서 raise e

    await load_system_prompts()

    print("✨ 서버 준비 완료")
    yield  # -------------------- [애플리케이션 가동 중] --------------------

    print("🛑 서버 종료 프로세스 가동...")
    await engine.dispose()
    print("👋 데이터베이스 연결 해제")

setup_logging()

app = FastAPI(lifespan=lifespan)

# middleware
middleware_config.set_cors_config(app)
app.add_middleware(StreamTrackerMiddleware)  # 스트림 추적
app.add_middleware(LoggingMiddleware)  # 로깅

# router
app.include_router(sse_router)
app.include_router(chat_session_router)

register_exception_handler(app)

# --- [Run] 실행 ---
if __name__ == '__main__':
    uvicorn.run("main:app", host='0.0.0.0', port=8000, reload=True)
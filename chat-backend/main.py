from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text

from config import middleware
from config.prompt import load_system_prompts
from config.swagger import setup_swagger
from middleware.logging import LoggingMiddleware
from middleware.stream_tracker import StreamTrackerMiddleware
from router import router as api_router
from common.exceptionhandler import register_exception_handler
from config.logger import setup_logging
from db.database import AsyncSessionLocal, engine  # DB 엔진 및 세션
from db.model_type_migration import ensure_model_type_schema
from mcp_hub import get_mcp_registry
from config.langfuse import init_langfuse_tracing


# --- [Lifespan] 서버 시작/종료 시 실행될 로직 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 서버 시작 프로세스 가동...")

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        print("✅ 데이터베이스 연결 성공")
        await ensure_model_type_schema(engine)
        print("✅ model_type 스키마 보강 완료")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        # DB 연결 실패 시 서버를 켜지 않으려면 여기서 raise e

    await load_system_prompts()

    # MCP Registry 초기화
    try:
        registry = get_mcp_registry()
        await registry.initialize()
    except Exception as e:
        print(f"⚠️ MCP Registry 초기화 실패 (서버는 계속 동작): {e}")

    # Langfuse OTEL 트레이싱 초기화
    init_langfuse_tracing()

    print("✨ 서버 준비 완료")
    yield  # -------------------- [애플리케이션 가동 중] --------------------

    print("🛑 서버 종료 프로세스 가동...")

    # MCP Registry 종료
    try:
        registry = get_mcp_registry()
        await registry.shutdown()
    except Exception as e:
        print(f"⚠️ MCP Registry 종료 실패: {e}")

    await engine.dispose()
    print("👋 데이터베이스 연결 해제")

setup_logging()

app = FastAPI(lifespan=lifespan)
app = setup_swagger(app, title="chat-server", version="0.0.1", description="chat-server")

# middleware
middleware.set_cors_config(app)
app.add_middleware(StreamTrackerMiddleware)  # 스트림 추적
app.add_middleware(LoggingMiddleware)  # 로깅

# router
app.include_router(api_router)

register_exception_handler(app)

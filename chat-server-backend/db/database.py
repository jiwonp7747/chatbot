from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# PostgreSQL 접속 정보 (본인 환경에 맞게 수정)
DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:30183/postgres"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Dependency Injection용 함수
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
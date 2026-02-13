from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def ensure_model_type_schema(engine: AsyncEngine) -> None:
    """
    model_type 테이블을 provider 기반 라우팅 구조로 보강합니다.
    """
    async with engine.begin() as conn:
        exists_result = await conn.execute(text("SELECT to_regclass('public.model_type')"))
        if exists_result.scalar() is None:
            return

        await conn.execute(text("""
            ALTER TABLE model_type
            ADD COLUMN IF NOT EXISTS provider VARCHAR(20)
        """))
        await conn.execute(text("""
            ALTER TABLE model_type
            ADD COLUMN IF NOT EXISTS api_model VARCHAR(200)
        """))
        await conn.execute(text("""
            ALTER TABLE model_type
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE
        """))
        await conn.execute(text("""
            UPDATE model_type
            SET provider = CASE
                WHEN provider IS NOT NULL THEN provider
                WHEN lower(model_type) LIKE 'gpt%' OR lower(model_type) LIKE 'o1%' OR lower(model_type) LIKE 'o3%' OR lower(model_type) LIKE 'o4%' THEN 'OPENAI'
                WHEN lower(model_type) LIKE 'gemini%' THEN 'GEMINI'
                WHEN lower(model_type) LIKE 'oci%' THEN 'OCI'
                WHEN lower(model_type) LIKE 'local%' OR lower(model_type) LIKE 'ollama%' OR lower(model_type) LIKE 'llama%' THEN 'LOCAL'
                ELSE 'OPENAI'
            END
        """))
        await conn.execute(text("""
            UPDATE model_type
            SET api_model = COALESCE(api_model, model_type)
        """))
        await conn.execute(text("""
            UPDATE model_type
            SET is_active = COALESCE(is_active, TRUE)
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_model_type_model_type
            ON model_type(model_type)
        """))

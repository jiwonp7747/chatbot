"""
DB 초기화 스크립트
- 테이블 생성 (chat_session, chat_message, model_type, prompt_template)
- 스키마 보강 (model_type provider/api_model/is_active)
- 시드 데이터 삽입/업데이트 (모델 목록, 기본 시스템 프롬프트)

Usage:
    python init_db.py
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
from sqlalchemy import text
from db.database import engine, Base, AsyncSessionLocal
from db.models import ChatSession, ChatMessage, ModelType, PromptTemplate
from db.model_type_migration import ensure_model_type_schema


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 테이블 생성 완료")


async def seed_models():
    async with AsyncSessionLocal() as session:
        oci_model_id = os.getenv("OCI_MODEL_ID", "").strip()

        # 이전 OCI 기본 모델(Command R) 엔트리는 비활성화
        await session.execute(text("""
            UPDATE model_type
            SET is_active = FALSE
            WHERE model_type = 'oci-command-r'
        """))

        await session.execute(text("""
            INSERT INTO model_type (model_name, model_type, provider, api_model, is_active, summary)
            VALUES
                ('GPT-5.1 Mini', 'gpt-5.1-mini', 'OPENAI', 'gpt-5.1-mini', TRUE, '균형형 기본 모델'),
                ('GPT-5 Nano', 'gpt-5-nano', 'OPENAI', 'gpt-5-nano', TRUE, '빠르고 효율적인 경량 모델'),
                ('GPT-4.1', 'gpt-4.1', 'OPENAI', 'gpt-4.1', TRUE, '강력한 추론 능력 모델'),
                ('Gemini Pro', 'gemini-pro', 'GEMINI', 'gemini-pro', FALSE, 'Google 모델 (레거시)'),
                ('Gemini 2.5 Pro', 'gemini-2.5-pro', 'GEMINI', 'gemini-2.5-pro', TRUE, 'Google 최강 추론 모델'),
                ('Gemini 2.5 Flash', 'gemini-2.5-flash', 'GEMINI', 'gemini-2.5-flash', TRUE, 'Google 빠른 추론 모델'),
                ('Gemini 2.0 Flash', 'gemini-2.0-flash', 'GEMINI', 'gemini-2.0-flash', TRUE, 'Google 경량 범용 모델'),
                ('OCI Llama 3.3 70B', 'oci-llama-3.3-70b', 'OCI', COALESCE(NULLIF(:oci_model_id, ''), 'meta.llama-3.3-70b-instruct'), TRUE, 'OCI Llama 모델'),
                ('Local Llama3.1', 'local-llama3.1', 'LOCAL', 'llama3.1:8b', FALSE, '로컬 모델 (구현 전)')
            ON CONFLICT (model_type) DO UPDATE SET
                model_name = EXCLUDED.model_name,
                provider = EXCLUDED.provider,
                api_model = EXCLUDED.api_model,
                is_active = EXCLUDED.is_active,
                summary = EXCLUDED.summary
        """), {"oci_model_id": oci_model_id})

        # 이전 OCI llama 3.1 키를 3.3 키로 승격
        await session.execute(text("""
            UPDATE model_type
            SET model_name = 'OCI Llama 3.3 70B',
                model_type = 'oci-llama-3.3-70b',
                api_model = COALESCE(NULLIF(:oci_model_id, ''), 'meta.llama-3.3-70b-instruct'),
                is_active = TRUE
            WHERE model_type = 'oci-llama-3.1-70b'
              AND NOT EXISTS (
                SELECT 1 FROM model_type t2 WHERE t2.model_type = 'oci-llama-3.3-70b'
              )
        """), {"oci_model_id": oci_model_id})

        # 3.3 키가 이미 있으면 3.1 키는 비활성화
        await session.execute(text("""
            UPDATE model_type
            SET is_active = FALSE
            WHERE model_type = 'oci-llama-3.1-70b'
              AND EXISTS (
                SELECT 1 FROM model_type t2 WHERE t2.model_type = 'oci-llama-3.3-70b'
              )
        """))
        await session.commit()
        print("✅ 모델 시드 데이터 삽입/업데이트 완료")


async def seed_prompts():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM prompt_template'))
        if result.scalar() > 0:
            print("⏭️  프롬프트 데이터 이미 존재 - 스킵")
            return

        await session.execute(text("""
            INSERT INTO prompt_template (prompt_name, prompt_type, is_active, priority, content) VALUES
            ('기본 시스템 프롬프트', 'system', true, 1,
             '당신은 Bistelligence AI의 도움이 되는 어시스턴트입니다. 사용자의 질문에 정확하고 친절하게 답변해주세요. 한국어로 답변합니다.')
        """))
        await session.commit()
        print("✅ 프롬프트 시드 데이터 삽입 완료 (1개)")


async def main():
    print("🚀 DB 초기화 시작...")
    await create_tables()
    await ensure_model_type_schema(engine)
    print("✅ model_type 스키마 보강 완료")
    await seed_models()
    await seed_prompts()
    await engine.dispose()
    print("✨ DB 초기화 완료")


if __name__ == "__main__":
    asyncio.run(main())

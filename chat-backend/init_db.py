"""
DB 초기화 스크립트
- 테이블 생성 (chat_session, chat_message, model_type, prompt_template)
- 시드 데이터 삽입 (모델 목록, 기본 시스템 프롬프트)

Usage:
    python init_db.py
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from sqlalchemy import text
from db.database import engine, Base, AsyncSessionLocal
from db.models import ChatSession, ChatMessage, ModelType, PromptTemplate


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 테이블 생성 완료")


async def seed_models():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM model_type'))
        if result.scalar() > 0:
            print("⏭️  모델 데이터 이미 존재 - 스킵")
            return

        await session.execute(text("""
            INSERT INTO model_type (model_name, model_type, summary) VALUES
            ('GPT-5 Nano', 'gpt-5-nano', '빠르고 효율적인 경량 모델'),
            ('GPT-4', 'gpt-4', '강력한 추론 능력의 대형 모델'),
            ('Claude 3', 'claude-3', 'Anthropic의 최신 AI 모델'),
            ('Gemini Pro', 'gemini-pro', 'Google의 멀티모달 AI 모델')
        """))
        await session.commit()
        print("✅ 모델 시드 데이터 삽입 완료 (4개)")


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
    await seed_models()
    await seed_prompts()
    await engine.dispose()
    print("✨ DB 초기화 완료")


if __name__ == "__main__":
    asyncio.run(main())

# global_state.py 또는 main.py 상단
from sqlalchemy import select, desc

from db.chat_models import PromptTemplate
from db.database import AsyncSessionLocal  # 세션 생성기 import

SYSTEM_PROMPT = "당신은 도움이 되는 AI 어시스턴트입니다."

async def load_system_prompts():
    """
    DB에서 is_active=True인 프롬프트를 우선순위(priority) 역순으로 가져와서
    하나의 문자열로 합칩니다.
    """
    global SYSTEM_PROMPT

    async with AsyncSessionLocal() as db:
        try:
            # 2. 쿼리 작성: 활성화된 것만, 우선순위 높은 순서대로
            query = (
                select(PromptTemplate)
                .where(PromptTemplate.is_active == True)
                .order_by(desc(PromptTemplate.priority))
            )
            result = await db.execute(query)
            prompts = result.scalars().all()

            if prompts:
                # 3. 여러 프롬프트 내용을 줄바꿈으로 연결하여 하나의 거대한 지침 생성
                combined_prompt = "\n\n".join([p.content for p in prompts])
                SYSTEM_PROMPT = combined_prompt
                print(f"✅ 시스템 프롬프트 로드 완료 ({len(prompts)}개 템플릿 적용)")
            else:
                print("⚠️ DB에 활성화된 프롬프트가 없습니다. 기본값을 사용합니다.")

        except Exception as e:
            print(f"❌ 프롬프트 로드 중 오류 발생: {e}")
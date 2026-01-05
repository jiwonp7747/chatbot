import asyncio

# AI Mock Method
async def fake_ai_generator(prompt: str):
    # 실제로는 여기서 OpenAI나 LLM 모델을 호출합니다.
    response_text = f"'{prompt}'에 대한 AI의 답변을 생성 중입니다... 이것은 스트리밍 테스트입니다."

    for word in response_text.split():
        # AI가 생각하는 시간 시뮬레이션 (0.1초~0.3초)
        await asyncio.sleep(0.1)

        # SSE 포맷 규격: "data: <메시지>\n\n"
        # 실제 데이터 앞에 'data: '를 붙이고 끝에 줄바꿈 두 번(\n\n)이 있어야 합니다.
        yield f"data: {word} \n\n"

    # 종료 신호 (선택 사항)
    yield "data: [DONE]\n\n"
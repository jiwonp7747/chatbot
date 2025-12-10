import json
from typing import AsyncGenerator
from client.openai_client import aclient
from schema import ChatRequest, ChatResponse, StreamStatus


async def process_chat_request(
        request: ChatRequest,
)->AsyncGenerator[str, None]:
    try:
        # 2. OpenAI API 호출 (stream=True가 핵심)
        stream = await aclient.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": "당신은 도움이 되는 AI 어시스턴트입니다."},
                {"role": "user", "content": request.prompt}
            ],
            stream=True  # 스트리밍 모드 활성화
        )

        # 3. 응답이 오는 대로 한 조각씩 클라이언트에게 전달
        async for chunk in stream:
            # 델타(변화량)에서 콘텐츠 추출
            content = chunk.choices[0].delta.content

            if content:
                # 1. 보낼 데이터를 딕셔너리로 구조화 (확장성 확보)
                response = ChatResponse(
                    content=content,
                    status=StreamStatus.STREAMING
                )

                # 2. JSON 문자열로 변환 (ensure_ascii=False는 한글 깨짐 방지 및 용량 절약)
                json_str = response.model_dump_json()

                # 3. SSE 포맷으로 전송
                yield f"data: {json_str}\n\n"

        done_response = ChatResponse(
            content="",
            status=StreamStatus.DONE
        )
        yield f"data: {done_response.model_dump_json()}\n\n"

    except Exception as e:
        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield f"data: Error: {str(e)}\n\n"
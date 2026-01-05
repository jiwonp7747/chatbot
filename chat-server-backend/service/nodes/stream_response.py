"""
노드 4: 응답 스트리밍

OpenAI API를 호출하고 스트리밍 응답을 생성합니다.
이 노드는 실제로는 AsyncGenerator로 동작하여 SSE 스트리밍을 지원합니다.
"""
import logging
from typing import AsyncGenerator
from starlette.requests import Request

from client.openai_client import aclient
from schema import ChatResponse, StreamStatus
from schema.chat_graph_schema import ChatGraphState
from sse.sse_util import SSEFormatter
from middleware.stream_tracker import update_stream_content

logger = logging.getLogger("chat-server")


async def stream_response_node(
    state: ChatGraphState,
    http_request: Request
) -> AsyncGenerator[str, None]:
    """
    OpenAI API를 호출하고 스트리밍 응답을 반환하는 노드

    Args:
        state: LangGraph 상태
        http_request: HTTP 요청 객체 (연결 상태 확인용)

    Yields:
        SSE 형식의 응답 청크
    """
    messages = state.get("messages", [])
    model = state.get("model", "gpt-5.1-mini")
    stream_id = state.get("stream_id")

    if not messages:
        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error="No messages to process"
        )
        yield SSEFormatter.format(error_response)
        return

    try:
        # OpenAI API 호출 (stream=True)
        stream = await aclient.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

        # 응답을 청크 단위로 스트리밍
        async for chunk in stream:
            # 연결 끊김 감지
            if await http_request.is_disconnected():
                logger.info(f"🔌 클라이언트 연결 끊김 감지: {stream_id}")
                await stream.aclose()
                logger.info(f"⚡ OpenAI 스트림 중단됨: {stream_id}")
                return

            # 델타(변화량) 추출
            content = chunk.choices[0].delta.content

            if content:
                # 전역 상태 업데이트 (DB 저장용)
                if stream_id:
                    update_stream_content(stream_id, content)

                # SSE 형식으로 응답
                response = ChatResponse(
                    content=content,
                    status=StreamStatus.STREAMING
                )
                yield SSEFormatter.format(response)

        # 스트리밍 정상 완료
        logger.info(f"✅ 스트리밍 정상 완료: {stream_id}")

        # DONE 상태 전송
        done_response = ChatResponse(
            content="",
            status=StreamStatus.DONE
        )
        yield SSEFormatter.format(done_response)

    except Exception as e:
        logger.error(f"❌ 스트리밍 에러: {stream_id}, {e}")

        error_response = ChatResponse(
            content="",
            status=StreamStatus.ERROR,
            error=str(e)
        )
        yield SSEFormatter.format(error_response)

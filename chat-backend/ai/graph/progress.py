"""
서브에이전트 진행 상황 사이드 채널

contextvars 기반으로 asyncio.Queue를 관리하여,
서브에이전트 내부 도구 호출 이벤트를 오케스트레이터에 전달합니다.
"""
import asyncio
from contextvars import ContextVar

_progress_queue: ContextVar[asyncio.Queue | None] = ContextVar(
    "_progress_queue", default=None
)


def set_progress_queue(queue: asyncio.Queue | None):
    """현재 컨텍스트에 progress queue 설정"""
    _progress_queue.set(queue)


def get_progress_queue() -> asyncio.Queue | None:
    """현재 컨텍스트의 progress queue 반환"""
    return _progress_queue.get(None)


async def emit_sub_progress(
    agent_name: str,
    tool_names: list[str],
    status: str = "calling",
):
    """서브에이전트 도구 진행 이벤트 발행

    queue가 설정되지 않은 경우 무시합니다 (fallback 안전).

    Args:
        agent_name: 서브에이전트 이름 (예: "fab_trace_agent")
        tool_names: 호출 중인 도구 이름 목록
        status: "calling" (호출 시작) 또는 "completed" (호출 완료)
    """
    queue = get_progress_queue()
    if queue is not None:
        await queue.put((
            "sub_progress",
            {
                "agent_name": agent_name,
                "tools": tool_names,
                "status": status,
                "parallel": len(tool_names) > 1,
            },
        ))


def emit_sub_progress_sync(
    agent_name: str,
    tool_names: list[str],
    status: str = "calling",
):
    """동기 버전 - 미들웨어의 wrap_tool_call (동기 메서드) 에서 사용

    asyncio.Queue.put_nowait()를 사용하므로 await 불필요.
    """
    queue = get_progress_queue()
    if queue is not None:
        queue.put_nowait((
            "sub_progress",
            {
                "agent_name": agent_name,
                "tools": tool_names,
                "status": status,
                "parallel": len(tool_names) > 1,
            },
        ))

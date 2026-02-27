"""
서브에이전트 도구 진행 상황 미들웨어

create_agent의 middleware 파라미터로 전달하여,
서브에이전트 내부 도구 호출/완료를 자동으로 감지하고
오케스트레이터에 sub_progress 이벤트를 발행합니다.

사용법:
    agent = create_agent(
        model=...,
        tools=...,
        middleware=[SubProgressMiddleware(agent_name="fab_trace_agent")],
    )
"""
import logging

from langchain.agents.middleware import AgentMiddleware
from ai.graph.progress import emit_sub_progress_sync, emit_sub_progress

logger = logging.getLogger("chat-server")


class SubProgressMiddleware(AgentMiddleware):
    """서브에이전트 도구 호출 진행 상황 자동 추적 미들웨어

    - aafter_model / after_model: LLM 응답에 tool_calls가 있으면 "calling" 이벤트 발행
      (병렬 호출 감지 가능 - 한 번에 여러 도구 이름 전달)
    - awrap_tool_call / wrap_tool_call: 개별 도구 실행 완료 시 "completed" 이벤트 발행

    비동기(ainvoke/astream)와 동기(invoke/stream) 모두 지원.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    # ── 비동기 버전 (ainvoke / astream 에서 호출됨) ──

    async def aafter_model(self, state, runtime):
        """[async] LLM 응답 후 tool_calls 감지 -> 'calling' 이벤트"""
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            names = [tc["name"] for tc in last_msg.tool_calls]
            await emit_sub_progress(self.agent_name, names, "calling")

        return None

    async def awrap_tool_call(self, request, handler):
        """[async] 도구 실행 래핑 -> 완료 시 'completed', 실패 시 'failed' 이벤트"""
        tool_name = request.tool_call.get("name", "unknown")

        try:
            result = await handler(request)
            await emit_sub_progress(self.agent_name, [tool_name], "completed")
            return result
        except Exception as e:
            await emit_sub_progress(self.agent_name, [tool_name], "failed")
            raise

    # ── 동기 버전 (invoke / stream 에서 호출됨) ──

    def after_model(self, state, runtime):
        """[sync] LLM 응답 후 tool_calls 감지 -> 'calling' 이벤트"""
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            names = [tc["name"] for tc in last_msg.tool_calls]
            emit_sub_progress_sync(self.agent_name, names, "calling")

        return None

    def wrap_tool_call(self, request, handler):
        """[sync] 도구 실행 래핑 -> 완료 시 'completed', 실패 시 'failed' 이벤트"""
        tool_name = request.tool_call.get("name", "unknown")

        try:
            result = handler(request)
            emit_sub_progress_sync(self.agent_name, [tool_name], "completed")
            return result
        except Exception as e:
            emit_sub_progress_sync(self.agent_name, [tool_name], "failed")
            raise

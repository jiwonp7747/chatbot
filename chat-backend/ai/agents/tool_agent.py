"""
MCP 도구 실행 전문 서브에이전트

MCP 서버에 등록된 도구(EChart, Memory 등)를 실행합니다.
as_tool()로 메인 에이전트의 도구로 사용됩니다.
"""
import logging

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from ai.agents.base import BaseAgent

logger = logging.getLogger("chat-server")

TOOL_AGENT_PROMPT = """당신은 도구 실행 전문가입니다.
차트 생성, 메모리 저장, 데이터 시각화 등 외부 도구를 실행합니다.

사용 가능한 도구 목록을 확인하고, 사용자의 요청에 가장 적합한 도구를 선택하세요.
도구 실행 결과를 사용자가 이해할 수 있도록 정리하여 반환하세요.
"""


class ToolAgent(BaseAgent):

    def __init__(self, model: str, mcp_tools: list = None):
        super().__init__(model)
        self._mcp_tools = mcp_tools or []

    def get_name(self) -> str:
        return "tool_agent"

    def get_description(self) -> str:
        return "차트 생성, 메모리 저장 등 MCP 도구를 실행합니다"

    def get_progress_label(self) -> str:
        return "⚡ 도구 실행 에이전트가 작업 중입니다..."

    def get_system_prompt(self) -> str:
        return TOOL_AGENT_PROMPT

    def get_tools(self) -> list:
        return self._mcp_tools

    def as_tool(self):
        """Tool 서브에이전트를 execute_tools 도구로 래핑"""
        agent = self.build()

        @tool
        async def execute_tools(request: str) -> str:
            """차트 생성, 메모리 저장, 데이터 시각화 등 외부 도구를 실행합니다.

            Args:
                request: 실행할 작업에 대한 설명 (예: "월별 매출 막대 차트를 만들어줘")
            """
            logger.info(f"⚡ Tool 서브에이전트 호출: {request[:50]}")
            result = await agent.ainvoke({
                "messages": [HumanMessage(content=request)]
            })
            return self.extract_ai_content(result)

        return execute_tools

"""
MCP → LangChain Tool 래퍼

MCP 서버에 등록된 도구들을 LangChain Tool 형식으로 변환합니다.
ToolAgent가 create_react_agent에서 사용할 수 있도록 합니다.
"""
import logging
from langchain_core.tools import StructuredTool

from mcp_hub import get_mcp_registry

logger = logging.getLogger("chat-server")


async def wrap_mcp_tools() -> list[StructuredTool]:
    """
    MCPRegistry의 모든 도구를 LangChain StructuredTool로 변환

    Returns:
        LangChain Tool 리스트
    """
    registry = get_mcp_registry()
    mcp_tools = await registry.list_all_tools()
    langchain_tools = []

    for mcp_tool in mcp_tools:
        tool_name = mcp_tool["name"]
        tool_desc = mcp_tool.get("description", "")

        async def _call(tool_name=tool_name, **kwargs):
            result = await registry.call_tool(tool_name, kwargs)
            if result.get("success"):
                content = result.get("result", {}).get("content", [])
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return "\n".join(texts) if texts else str(result)
            return f"도구 실행 실패: {result.get('error', 'unknown')}"

        langchain_tools.append(
            StructuredTool.from_function(
                coroutine=_call,
                name=tool_name,
                description=tool_desc,
            )
        )

    logger.info(f"🔧 MCP → LangChain Tool 변환 완료: {len(langchain_tools)}개")
    return langchain_tools

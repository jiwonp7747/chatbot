"""
노드 0: MCP 도구 목록 조회

MCPRegistry를 통해 모든 MCP 서버의 사용 가능한 도구 목록을 가져옵니다.
"""
import logging
from typing import Dict, Any

from ai.graph.schema.graph_state import ChatGraphState
from mcp_hub import get_mcp_registry

logger = logging.getLogger("chat-server")


async def load_available_tools_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    MCPRegistry에서 사용 가능한 도구 목록을 조회하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (available_tools 포함)
    """
    try:
        registry = get_mcp_registry()
        available_tools = await registry.list_all_tools()

        logger.info(f"📋 사용 가능한 도구: {len(available_tools)}개")
        for tool in available_tools:
            logger.info(f"  - [{tool.get('source', '?')}] {tool['name']}: {tool['description']}")

        return {
            "available_tools": available_tools
        }

    except Exception as e:
        logger.error(f"❌ MCP 도구 목록 조회 실패: {e}")
        import traceback
        traceback.print_exc()

        return {
            "available_tools": []
        }

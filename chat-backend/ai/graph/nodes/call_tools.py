"""
노드 3: MCP 도구 호출

MCPRegistry를 통해 필요한 도구들을 호출하고 결과를 수집합니다.
"""
import logging
from typing import Dict, Any

from ai.graph.schema.graph_state import ChatGraphState
from mcp_hub import get_mcp_registry

logger = logging.getLogger("chat-server")


async def call_tools_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    MCPRegistry를 통해 도구를 호출하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (tool_results 포함)
    """
    try:
        tools_to_call = state.get("tools_to_call", [])
        tool_results = state.get("tool_results", [])

        if not tools_to_call:
            logger.info("ℹ️ 호출할 도구가 없습니다")
            return {"tool_results": tool_results}

        logger.info(f"🔧 도구 호출 시작: {len(tools_to_call)}개")
        registry = get_mcp_registry()

        for tool_call in tools_to_call:
            tool_name = tool_call.get("name")
            tool_arguments = tool_call.get("arguments", {})

            # token 자동 주입 (AI가 빼먹은 경우 대비)
            if 'token' not in tool_arguments:
                token = state.get('token')
                if token:
                    tool_arguments['token'] = token
                    logger.info(f"🔑 Token 자동 주입: {tool_name}")

            try:
                logger.info(f"🔨 도구 호출: {tool_name} (arguments: {list(tool_arguments.keys())})")
                result = await registry.call_tool(tool_name, tool_arguments)
                tool_results.append(result)

            except Exception as e:
                logger.error(f"❌ 도구 호출 실패: {tool_name}, {e}")
                tool_results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                    "result": None
                })

        success_count = sum(1 for r in tool_results if r.get('success'))
        logger.info(f"🎉 도구 호출 완료: 성공 {success_count}/{len(tools_to_call)}")

        return {
            "tool_results": tool_results,
            "tools_to_call": []
        }

    except Exception as e:
        logger.error(f"❌ call_tools_node 최상위 에러: {e}")
        import traceback
        traceback.print_exc()
        return {
            "tool_results": [],
            "error": f"call_tools_node error: {str(e)}"
        }

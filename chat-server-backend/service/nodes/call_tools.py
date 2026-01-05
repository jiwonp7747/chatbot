"""
노드 3: MCP 도구 호출

MCP 서버에 연결하여 필요한 도구들을 호출하고 결과를 수집합니다.
"""
import logging
import os
from typing import Dict, Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from schema.chat_graph_schema import ChatGraphState

logger = logging.getLogger("chat-server")

# 환경 변수에서 MCP 서버 URL 가져오기 (기본값: localhost:3000)
MCP_SERVER_SSE_URL = os.getenv("MCP_SERVER_SSE_URL", "http://localhost:3000/sse")


async def call_tools_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    MCP 서버에 연결하여 도구를 호출하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (tool_results 포함)
    """
    try:
        tools_to_call = state.get("tools_to_call", [])
        tool_results = state.get("tool_results", [])

        # 호출할 도구가 없으면 스킵
        if not tools_to_call:
            logger.info("ℹ️ 호출할 도구가 없습니다")
            return {
                "tool_results": tool_results
            }

        logger.info(f"🔧 도구 호출 시작: {len(tools_to_call)}개")

        try:
            # SSE 클라이언트 연결
            async with sse_client(MCP_SERVER_SSE_URL) as (read, write):
                async with ClientSession(read, write) as session:
                    # 세션 초기화
                    await session.initialize()
                    logger.info(f"✅ MCP 서버 연결 성공: {MCP_SERVER_SSE_URL}")

                    # 각 도구 호출
                    for tool_call in tools_to_call:
                        tool_name = tool_call.get("name")
                        tool_arguments = tool_call.get("arguments", {})

                        # ✅ token 자동 주입 (AI가 빼먹은 경우 대비)
                        if 'token' not in tool_arguments:
                            token = state.get('token')
                            if token:
                                tool_arguments['token'] = token
                                logger.info(f"🔑 Token 자동 주입됨: {tool_name}")
                        else:
                            logger.info(f"✓ Token 이미 존재: {tool_name}")

                        try:
                            logger.info(f"🔨 도구 호출: {tool_name} (arguments: {list(tool_arguments.keys())})")

                            # 도구 실행
                            result = await session.call_tool(
                                tool_name,
                                arguments=tool_arguments
                            )

                            # MCP 서버 자체 에러 체크
                            if getattr(result, 'isError', False):
                                error_msg = f"MCP Server Error: {result.content}"
                                logger.error(f"❌ 도구 실행 에러: {tool_name}, {error_msg}")
                                tool_results.append({
                                    "tool": tool_name,
                                    "success": False,
                                    "error": error_msg,
                                    "result": None
                                })
                                continue

                            # 결과 파싱
                            parsed_result = _parse_tool_result(result)

                            logger.info(f"✅ 도구 실행 성공: {tool_name}")
                            tool_results.append({
                                "tool": tool_name,
                                "success": True,
                                "error": None,
                                "result": parsed_result
                            })

                        except Exception as e:
                            logger.error(f"❌ 도구 호출 실패: {tool_name}, {e}")
                            tool_results.append({
                                "tool": tool_name,
                                "success": False,
                                "error": str(e),
                                "result": None
                            })

            logger.info(f"🎉 도구 호출 완료: 성공 {sum(1 for r in tool_results if r['success'])}/{len(tools_to_call)}")

            return {
                "tool_results": tool_results,
                "tools_to_call": []  # 호출 완료 후 초기화
            }

        except Exception as e:
            logger.error(f"❌ MCP 서버 연결 실패: {e}")
            return {
                "tool_results": tool_results,
                "error": f"Failed to connect to MCP server: {str(e)}"
            }

    except Exception as e:
        logger.error(f"❌ call_tools_node 최상위 에러: {e}")
        import traceback
        traceback.print_exc()
        return {
            "tool_results": [],
            "error": f"call_tools_node error: {str(e)}"
        }


def _parse_tool_result(result) -> Dict[str, Any]:
    """
    MCP 도구 실행 결과를 파싱

    Args:
        result: MCP 도구 실행 결과

    Returns:
        파싱된 결과
    """
    parsed = {
        "content": [],
        "metadata": {}
    }

    if not hasattr(result, 'content'):
        return parsed

    for content_item in result.content:
        content_type = content_item.type

        if content_type == "text":
            parsed["content"].append({
                "type": "text",
                "text": content_item.text
            })
        elif content_type == "image":
            parsed["content"].append({
                "type": "image",
                "data": content_item.data,
                "mimeType": getattr(content_item, 'mimeType', 'image/png')
            })
        elif content_type == "resource":
            parsed["content"].append({
                "type": "resource",
                "uri": getattr(content_item, 'uri', None),
                "text": getattr(content_item, 'text', None)
            })
        else:
            # 기타 타입
            parsed["content"].append({
                "type": content_type,
                "raw": str(content_item)
            })

    return parsed

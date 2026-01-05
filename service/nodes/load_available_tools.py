"""
노드 0: MCP 도구 목록 조회

MCP 서버에 연결하여 사용 가능한 도구 목록을 가져옵니다.
"""
import logging
import os
from typing import Dict, Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from schema.chat_graph_schema import ChatGraphState

logger = logging.getLogger("chat-server")

# 환경 변수에서 MCP 서버 URL 가져오기
MCP_SERVER_SSE_URL = os.getenv("MCP_SERVER_SSE_URL", "http://localhost:3000/sse")


async def load_available_tools_node(
    state: ChatGraphState
) -> Dict[str, Any]:
    """
    MCP 서버에서 사용 가능한 도구 목록을 조회하는 노드

    Args:
        state: LangGraph 상태

    Returns:
        업데이트된 상태 (available_tools 포함)
    """
    try:
        logger.info(f"🔧 MCP 서버 연결 시작: {MCP_SERVER_SSE_URL}")

        # SSE 클라이언트 연결
        async with sse_client(MCP_SERVER_SSE_URL) as (read, write):
            async with ClientSession(read, write) as session:
                # 세션 초기화
                await session.initialize()
                logger.info("✅ MCP 서버 연결 성공")

                # 사용 가능한 도구 목록 조회
                tools_list = await session.list_tools()

                # 도구 정보를 딕셔너리 형태로 변환
                available_tools = []
                for tool in tools_list.tools:
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                    }
                    available_tools.append(tool_info)

                logger.info(f"📋 사용 가능한 도구: {len(available_tools)}개")
                for tool in available_tools:
                    logger.info(f"  - {tool['name']}: {tool['description']}")

                return {
                    "available_tools": available_tools
                }

    except Exception as e:
        logger.error(f"❌ MCP 도구 목록 조회 실패: {e}")
        import traceback
        traceback.print_exc()

        # 실패해도 빈 리스트로 계속 진행
        return {
            "available_tools": [],
            "error": f"Failed to load available tools: {str(e)}"
        }

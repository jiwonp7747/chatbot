"""SSE 전송 기반 MCP 어댑터"""
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from .adapter import MCPAdapter

logger = logging.getLogger("chat-server")


def _get_tool_description(tool) -> str:
    """도구 설명 추출 헬퍼"""
    if tool.description:
        return tool.description
    if hasattr(tool, 'annotations') and tool.annotations and tool.annotations.description:
        return tool.annotations.description
    return "설명이 없는 도구입니다."


class SSEAdapter(MCPAdapter):
    """SSE 전송 기반 MCP 어댑터"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.url: str = config.get("url", "")
        self.auth = config.get("auth")

    async def connect(self) -> None:
        """SSE 서버 연결 확인 및 도구 목록 캐싱"""
        try:
            logger.info(f"🔌 [{self.name}] SSE 서버 연결 시도: {self.url}")
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_list = await session.list_tools()
                    self._tools = []
                    for tool in tools_list.tools:
                        tool_info = {
                            "name": tool.name,
                            "description": _get_tool_description(tool),
                            "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                            "source": self.name,
                        }
                        self._tools.append(tool_info)
            logger.info(f"✅ [{self.name}] 연결 성공, {len(self._tools)}개 도구 발견")
        except Exception as e:
            logger.error(f"❌ [{self.name}] 연결 실패: {e}")
            self._tools = []

    async def list_tools(self) -> list[dict]:
        """캐시된 도구 목록 반환"""
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """SSE 연결로 도구 호출"""
        try:
            logger.info(f"🔨 [{self.name}] 도구 호출: {tool_name}")
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)

                    if getattr(result, 'isError', False):
                        error_msg = f"MCP Server Error: {result.content}"
                        logger.error(f"❌ [{self.name}] 도구 에러: {tool_name}, {error_msg}")
                        return {"success": False, "error": error_msg, "result": None}

                    parsed = self._parse_result(result)
                    logger.info(f"✅ [{self.name}] 도구 성공: {tool_name}")
                    return {"success": True, "error": None, "result": parsed}

        except Exception as e:
            logger.error(f"❌ [{self.name}] 도구 호출 실패: {tool_name}, {e}")
            return {"success": False, "error": str(e), "result": None}

    async def disconnect(self) -> None:
        """SSE는 요청별 연결이므로 별도 disconnect 불필요"""
        logger.info(f"🔌 [{self.name}] 어댑터 종료")
        self._tools = []

    @staticmethod
    def _parse_result(result) -> dict[str, Any]:
        """MCP 도구 실행 결과 파싱"""
        parsed: dict[str, Any] = {"content": [], "metadata": {}}
        if not hasattr(result, 'content'):
            return parsed
        for item in result.content:
            if item.type == "text":
                parsed["content"].append({"type": "text", "text": item.text})
            elif item.type == "image":
                parsed["content"].append({
                    "type": "image",
                    "data": item.data,
                    "mimeType": getattr(item, 'mimeType', 'image/png')
                })
            elif item.type == "resource":
                parsed["content"].append({
                    "type": "resource",
                    "uri": getattr(item, 'uri', None),
                    "text": getattr(item, 'text', None)
                })
            else:
                parsed["content"].append({"type": item.type, "raw": str(item)})
        return parsed

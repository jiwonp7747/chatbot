"""Stdio 전송 기반 MCP 어댑터 (향후 확장용)"""
import logging
from .adapter import MCPAdapter

logger = logging.getLogger("chat-server")


class StdioAdapter(MCPAdapter):
    """Stdio 전송 기반 MCP 어댑터 스켈레톤"""

    async def connect(self) -> None:
        logger.warning(f"⚠️ [{self.name}] Stdio 어댑터는 아직 구현되지 않았습니다")

    async def list_tools(self) -> list[dict]:
        return []

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        return {"success": False, "error": "Stdio adapter not implemented", "result": None}

    async def disconnect(self) -> None:
        pass

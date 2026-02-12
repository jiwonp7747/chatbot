"""MCP 멀티소스 레지스트리 — 여러 MCP 서버의 도구를 통합 관리"""
import logging
from typing import Optional

from .adapter import MCPAdapter
from .config import load_mcp_config
from .sse_adapter import SSEAdapter
from .stdio_adapter import StdioAdapter

logger = logging.getLogger("chat-server")

# 싱글턴 인스턴스
_registry_instance: Optional["MCPRegistry"] = None


class MCPRegistry:
    """여러 MCP 서버의 도구를 통합 관리하는 레지스트리"""

    def __init__(self):
        self.adapters: dict[str, MCPAdapter] = {}
        self.tool_map: dict[str, str] = {}  # tool_name → server_name

    async def initialize(self, config_path: Optional[str] = None) -> None:
        """mcp_servers.json에서 설정 로드 → 어댑터 생성 → 연결"""
        config = load_mcp_config(config_path)

        for name, server_config in config.mcp_servers.items():
            if not server_config.enabled:
                logger.info(f"⏭️ [{name}] 비활성화 — 스킵")
                continue

            adapter = self._create_adapter(name, server_config.model_dump())
            if adapter is None:
                continue

            await adapter.connect()
            self.adapters[name] = adapter

            # 도구 맵 구축
            for tool in await adapter.list_tools():
                tool_name = tool["name"]
                if tool_name in self.tool_map:
                    logger.warning(
                        f"⚠️ 도구 이름 충돌: {tool_name} "
                        f"({self.tool_map[tool_name]} vs {name}) — {name} 우선"
                    )
                self.tool_map[tool_name] = name

        total_tools = len(self.tool_map)
        total_servers = len(self.adapters)
        logger.info(f"✅ MCP Registry 초기화 완료: {total_servers}개 서버, {total_tools}개 도구")

    def _create_adapter(self, name: str, config: dict) -> Optional[MCPAdapter]:
        """전송 타입에 따른 어댑터 생성"""
        transport = config.get("transport", "sse")
        if transport == "sse":
            return SSEAdapter(name, config)
        elif transport == "stdio":
            return StdioAdapter(name, config)
        else:
            logger.error(f"❌ [{name}] 지원하지 않는 전송 타입: {transport}")
            return None

    async def list_all_tools(self) -> list[dict]:
        """모든 서버의 도구를 모아서 반환"""
        all_tools = []
        for adapter in self.adapters.values():
            all_tools.extend(await adapter.list_tools())
        return all_tools

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """tool_name으로 올바른 서버를 찾아 호출"""
        server_name = self.tool_map.get(tool_name)
        if not server_name:
            logger.error(f"❌ 도구를 찾을 수 없음: {tool_name}")
            return {
                "tool": tool_name,
                "success": False,
                "error": f"Tool '{tool_name}' not found in any MCP server",
                "result": None
            }

        adapter = self.adapters.get(server_name)
        if not adapter:
            return {
                "tool": tool_name,
                "success": False,
                "error": f"Adapter '{server_name}' not available",
                "result": None
            }

        result = await adapter.call_tool(tool_name, arguments)
        result["tool"] = tool_name
        return result

    async def shutdown(self) -> None:
        """모든 어댑터 연결 해제"""
        for name, adapter in self.adapters.items():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"❌ [{name}] 종료 실패: {e}")
        self.adapters.clear()
        self.tool_map.clear()
        logger.info("🛑 MCP Registry 종료 완료")


def get_mcp_registry() -> MCPRegistry:
    """싱글턴 레지스트리 인스턴스 반환"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = MCPRegistry()
    return _registry_instance

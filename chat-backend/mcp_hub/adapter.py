"""MCP 어댑터 추상 클래스"""
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("chat-server")

class MCPAdapter(ABC):
    """MCP 서버 연결 어댑터 추상 클래스"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self._tools: list[dict] = []

    @abstractmethod
    async def connect(self) -> None:
        """MCP 서버에 연결"""
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict]:
        """사용 가능한 도구 목록 조회"""
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """도구 호출"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """연결 해제"""
        ...

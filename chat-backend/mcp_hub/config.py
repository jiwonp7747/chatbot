"""MCP 서버 설정 로더 및 검증"""
import json
import os
from typing import Optional
from pydantic import BaseModel, Field

class AuthConfig(BaseModel):
    type: str = "bearer"
    token_from_header: Optional[str] = Field(None, alias="tokenFromHeader")

class MCPServerConfig(BaseModel):
    transport: str  # "sse", "stdio", or "streamable-http"
    url: Optional[str] = None  # SSE transport
    command: Optional[str] = None  # Stdio transport
    args: list[str] = Field(default_factory=list)
    description: str = ""
    enabled: bool = True
    auth: Optional[AuthConfig] = None

    model_config = {"populate_by_name": True}

class MCPServersConfig(BaseModel):
    mcp_servers: dict[str, MCPServerConfig] = Field(alias="mcpServers")

    model_config = {"populate_by_name": True}

def load_mcp_config(config_path: Optional[str] = None) -> MCPServersConfig:
    """mcp_servers.json 설정 파일 로드"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp_servers.json")

    if not os.path.exists(config_path):
        # 설정 파일이 없으면 빈 설정 반환
        return MCPServersConfig(mcpServers={})

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return MCPServersConfig(**data)

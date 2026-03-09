"""MCP 도구 실행 서브에이전트 설정

MCP 서버에 등록된 도구(EChart, Memory 등)를 실행합니다.
create_deep_agent의 subagents 파라미터용 SubAgent 딕셔너리를 반환합니다.
"""

TOOL_AGENT_PROMPT = """당신은 도구 실행 전문가입니다.
차트 생성, 메모리 저장, 데이터 시각화 등 외부 도구를 실행합니다.

사용 가능한 도구 목록을 확인하고, 사용자의 요청에 가장 적합한 도구를 선택하세요.
도구 실행 결과를 사용자가 이해할 수 있도록 정리하여 반환하세요.
"""


def create_tool_subagent(mcp_tools: list, middleware: list | None = None):
    """MCP 도구 실행 서브에이전트 SubAgent 딕셔너리 반환"""
    spec = {
        "name": "execute-tools",
        "description": "차트 생성, 메모리 저장 등 MCP 도구를 실행합니다",
        "system_prompt": TOOL_AGENT_PROMPT,
        "tools": mcp_tools,
    }
    if middleware:
        spec["middleware"] = middleware
    return spec

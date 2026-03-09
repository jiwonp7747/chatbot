"""RAG 검색 서브에이전트 설정

업로드된 문서에서 태그 기반 + 시맨틱 검색을 수행합니다.
create_deep_agent의 subagents 파라미터용 SubAgent 딕셔너리를 반환합니다.
"""
from ai.tools.rag import get_rag_tools
from ai.hitl import build_hitl_confirm_description

RAG_AGENT_PROMPT = """당신은 문서 검색 전문가입니다.
사용자의 질문에 관련된 문서를 정확하게 찾아 핵심 내용을 정리하세요.

도구 사용 규칙 (반드시 준수):
- 태그가 지정된 경우 → tag_search_tool만 사용
- 태그 없이 일반 검색 → semantic_search_tool만 사용
- 한 번의 요청에 도구를 1개만 호출하세요. 두 도구를 동시에 사용하지 마세요.
- 도구를 호출해야 할 때는, 호출 직전에 반드시 아래 2줄을 먼저 작성한 뒤 도구를 호출하세요.
  도구 선택 이유: (현재 질문/단계 기준으로 왜 이 도구가 필요한지 1~2문장)
  예상 결과: (이 도구 호출로 어떤 데이터를 확인하고, 그 결과로 다음에 무엇을 판단할지 1~2문장)
- 위 2줄은 구체적으로 작성하세요. "필요해서", "도움될 것" 같은 추상 표현은 금지합니다.

사용자 수정 요청 (최우선 규칙):
- 사용자가 도구 호출을 거부(reject)하거나 수정(edit) 요청을 보내면, 그 지시를 반드시 따르세요.
- 거부된 도구를 같은 인자로 다시 호출하는 것은 금지입니다.
- 사용자 메시지에 구체적인 지시가 있으면 그대로 실행하세요.

검색 결과를 그대로 나열하지 말고, 사용자 질문에 맞게 요약하여 답변하세요.
"""


def create_rag_subagent():
    """RAG 서브에이전트 SubAgent 딕셔너리 반환"""
    def hitl_description(tool_call, state, runtime):
        return build_hitl_confirm_description(tool_call, state, runtime, domain="rag")

    return {
        "name": "search-documents",
        "description": "업로드된 문서에서 정보를 검색하고 관련 내용을 찾습니다",
        "system_prompt": RAG_AGENT_PROMPT,
        "tools": get_rag_tools(),
        "interrupt_on": {
            "tag_search_tool": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "semantic_search_tool": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
        },
    }

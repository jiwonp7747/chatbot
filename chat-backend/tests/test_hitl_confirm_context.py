from langchain_core.messages import AIMessage, HumanMessage

from ai.graph.orchestrator import _build_interrupt_tool_context
from ai.hitl import build_hitl_confirm_description


def test_build_hitl_confirm_description_contains_required_sections():
    tool_call = {"name": "semantic_search_tool", "args": {"query": "수율 하락", "n_results": 3}}
    state = {
        "messages": [
            HumanMessage(content="최근 수율 하락 원인을 문서에서 찾아줘"),
            AIMessage(content="관련 문서를 찾기 위해 의미 기반 검색을 먼저 수행하겠습니다."),
        ]
    }

    description = build_hitl_confirm_description(tool_call, state, runtime=None, domain="rag")

    assert "실행 예정 도구" in description
    assert "semantic_search_tool" in description
    assert '"query": "수율 하락"' in description


def test_build_hitl_confirm_description_uses_fallback_without_messages():
    description = build_hitl_confirm_description(
        {"name": "unknown_tool", "args": {}},
        state={},
        runtime=None,
        domain="rag",
    )

    assert "현재 요청을 처리하기 위해 이 도구 호출이 필요하다고 판단했습니다." in description


def test_interrupt_context_prefers_description_for_single_tool():
    action_requests = [{"name": "tag_search_tool", "description": "설명 텍스트"}]
    context = _build_interrupt_tool_context(action_requests, fallback_reasoning="fallback")
    assert context == "설명 텍스트"


def test_interrupt_context_merges_parallel_descriptions():
    action_requests = [
        {"name": "get_defect_map", "description": "좌표 분포를 확인합니다."},
        {"name": "get_defects", "description": "LOT 상세를 확인합니다."},
    ]
    context = _build_interrupt_tool_context(action_requests, fallback_reasoning="fallback")

    assert "[1] get_defect_map" in context
    assert "좌표 분포를 확인합니다." in context
    assert "[2] get_defects" in context
    assert "LOT 상세를 확인합니다." in context


def test_interrupt_context_falls_back_when_description_missing():
    action_requests = [{"name": "semantic_search_tool"}]
    context = _build_interrupt_tool_context(action_requests, fallback_reasoning="기존 추론")
    assert context == "기존 추론"

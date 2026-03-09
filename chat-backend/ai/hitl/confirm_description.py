"""HITL confirm description 생성 유틸리티."""

from __future__ import annotations

import json
from typing import Any, Mapping

from langchain_core.messages import AIMessage

_MAX_REASON_LEN = 700
_MAX_ARGS_LEN = 900

_DEFAULT_REASON = "현재 요청을 처리하기 위해 이 도구 호출이 필요하다고 판단했습니다."
_DEFAULT_EXPECTED_RESULT = "다음 답변을 구성하는 데 필요한 근거 데이터를 확보합니다."

_TOOL_EXPECTED_RESULT: dict[str, str] = {
    "tag_search_tool": "지정한 태그 범위에서 관련 문서를 좁혀 핵심 근거를 빠르게 식별합니다.",
    "semantic_search_tool": "전체 문서에서 질문과 의미적으로 가까운 근거 문서를 확보합니다.",
    "get_defect_summary": "급증한 불량 유형과 규모를 파악해 원인 분석의 시작점을 정합니다.",
    "get_defect_map": "불량 좌표 분포 패턴을 확인해 공정/설비 이상 유형을 좁힙니다.",
    "get_defects": "불량이 집중된 LOT와 상세 데이터를 확보해 역추적 대상을 특정합니다.",
    "get_fdc_traceback": "의심 LOT의 설비/파라미터 이력을 추적해 원인 후보를 식별합니다.",
    "get_equipment_health": "의심 설비의 건강도와 알람/OOS 현황을 점검해 이상 여부를 판단합니다.",
    "get_trace_summary": "설비 파라미터의 통계와 OOS 비율을 확인해 안정성을 수치로 검증합니다.",
    "get_param_drift": "시간대별 파라미터 편차 추이를 확인해 이탈 시점을 식별합니다.",
    "get_trace_compare": "동일 타입 설비 간 편차를 비교해 개별 설비 문제인지 확인합니다.",
}


def _to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return str(content) if content else ""


def _trim(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


def _extract_reason(messages: list[Any], tool_name: str) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = _to_text(getattr(msg, "content", "")).strip()
            if content:
                return _trim(content, _MAX_REASON_LEN)
    return f"{_DEFAULT_REASON} ('{tool_name}')"


def _format_args(args: Any) -> str:
    try:
        encoded = json.dumps(args, ensure_ascii=False, default=str)
    except Exception:
        encoded = str(args)
    if len(encoded) <= _MAX_ARGS_LEN:
        return encoded
    return f"{encoded[: _MAX_ARGS_LEN - 3]}..."


def _expected_result(tool_name: str) -> str:
    return _TOOL_EXPECTED_RESULT.get(tool_name, _DEFAULT_EXPECTED_RESULT)


def build_hitl_confirm_description(
    tool_call: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    runtime: Any,  # noqa: ARG001 - LangChain callable 시그니처 유지용
    domain: str | None = None,  # noqa: ARG001 - 향후 도메인별 규칙 확장용
) -> str:
    """HITL confirm용 설명 텍스트를 JSON 문자열로 생성합니다.

    반환 형식 (JSON string):
      {"reason": "에이전트 추론 내용", "tool_detail": "도구 상세 정보"}

    병렬 interrupt 시 orchestrator가 reason을 한번만 표시하고
    tool_detail만 개별 나열할 수 있도록 분리합니다.
    """
    tool_name = str(tool_call.get("name", "unknown"))
    tool_args = tool_call.get("args", {})

    messages = list((state or {}).get("messages", []) or [])
    reason = _extract_reason(messages, tool_name)
    args_text = _format_args(tool_args)
    expected = _expected_result(tool_name)

    tool_detail = {
        "tool_name": tool_name,
        "description": expected,
        "args": args_text,
    }

    return json.dumps({"reason": reason, "tool_detail": tool_detail}, ensure_ascii=False)

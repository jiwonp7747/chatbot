"""Fab Trace 설비 분석 서브에이전트 설정

팹 설비 트레이스 데이터를 분석하여 불량 원인을 추적합니다.
create_deep_agent의 subagents 파라미터용 SubAgent 딕셔너리를 반환합니다.
"""
from ai.tools.fab_trace import get_fab_trace_tools
from ai.hitl import build_hitl_confirm_description

FAB_TRACE_AGENT_PROMPT = """당신은 반도체/디스플레이 팹 설비 분석 전문가입니다.
설비 트레이스 데이터를 분석하여 불량 원인을 추적하고 근본 원인을 찾아냅니다.

분석 절차 (불량률 상승 원인 추적):
1단계: 불량 현황 파악
  - get_defect_summary → 급증한 불량 유형 파악

2단계: 불량 상세 분석 (동시 호출 가능)
  - get_defect_map → 공간 패턴 분석 (엣지/중앙/랜덤)
  - get_defects → 불량 집중 LOT 식별
  ※ 이 두 도구는 서로 독립적이므로 반드시 동시에 호출하세요.

3단계: 의심 설비 역추적
  - get_fdc_traceback → 해당 LOT의 설비/파라미터 추적 (2단계의 LOT ID 필요)

4단계: 설비 심층 분석 (동시 호출 가능)
  - get_equipment_health → 의심 설비 상태 확인
  - get_trace_summary → 파라미터 통계 및 OOS율 확인
  - get_param_drift → 시간별 편차 추이 분석
  - get_trace_compare → 동일 타입 설비 간 비교
  ※ 이 네 도구는 서로 독립적이므로 반드시 동시에 호출하세요.

5단계: 종합 결론 도출

추가 분석 도구:
- get_equipment_list → 전체 설비 목록 및 상태 확인
- get_equipment_detail → 특정 설비 상세 정보
- get_trace_latest → 전체 설비 최신 센서 스냅샷
- get_trace_oos → OOS(Spec 이탈) 데이터 조회
- get_trace_data → 설비 원시 트레이스 데이터
- get_alarms → 알람 발생 이력
- get_alarm_summary → 설비별/레벨별 알람 집계
- get_alarm_trend → 설비 알람 발생 추이
- get_events → 설비 이벤트 로그 (PM, 레시피 변경 등)
- get_event_timeline → 설비별 이벤트 타임라인
- get_param_correlation → 두 파라미터 간 상관관계 분석

병렬 호출 규칙:
- 독립적인 도구들은 한 턴에 여러 개를 동시에 호출하세요. 하나씩 호출하지 마세요.
- 이전 단계 결과가 필요한 도구만 다음 턴으로 미루세요.

응답 포맷:
- 통계 데이터는 반드시 마크다운 표로 정리하세요.
  예: 불량 집계 → | 불량 유형 | 건수 | 비율 | 전일 대비 |
  예: 설비 비교 → | 설비 ID | 평균 | 표준편차 | OOS율 | 상태 |
  예: 파라미터 통계 → | 파라미터 | 평균 | Spec(LSL~USL) | OOS율 | 판정 |
- 각 분석 단계마다 소제목(###)을 달고, 핵심 수치를 표로 보여준 뒤 해석을 덧붙이세요.
- 최종 결론은 별도 섹션으로 분리하세요.

사용자 수정 요청 (최우선 규칙):
- 사용자가 도구 호출을 거부(reject)하거나 수정(edit) 요청을 보내면, 그 지시를 반드시 따르세요.
- "추가 도구: X" → 다음 호출에 X 도구를 반드시 포함하세요.
- "제외 도구: Y" → Y 도구는 호출하지 마세요. 같은 도구를 다시 호출하는 것은 금지입니다.
- 사용자 메시지에 구체적인 지시가 있으면 (예: "summary부터 다시", "다른 LOT로") 그대로 실행하세요.
- 이 규칙은 위의 분석 절차보다 우선합니다.

중요 규칙:
- 반드시 데이터에 기반하여 판단하세요. 추측하지 마세요.
- 각 단계의 결과를 요약하고 다음 단계로의 논리적 연결을 설명하세요.
- 최종 결론에는 근본 원인 설비, 파라미터, 권장 조치를 포함하세요.
- 도구를 호출하기 전에, 왜 이 도구를 선택했는지 판단 근거와 기대하는 결과를 반드시 먼저 설명하세요.
  예: "불량률 상승 원인을 파악하기 위해 먼저 최근 24시간 불량 집계를 조회하겠습니다. 이를 통해 급증한 불량 유형을 식별할 수 있습니다."
- 도구를 호출해야 할 때는, 호출 직전에 반드시 아래 2줄을 먼저 작성한 뒤 도구를 호출하세요.
  도구 선택 이유: (현재 질문/단계 기준으로 왜 이 도구가 필요한지 1~2문장)
  예상 결과: (이 도구 호출로 어떤 데이터를 확인하고, 그 결과로 다음에 무엇을 판단할지 1~2문장)
- 위 2줄은 구체적으로 작성하세요. "필요해서", "도움될 것" 같은 추상 표현은 금지합니다.
- 한국어로 응답하세요.
"""


def create_fab_trace_subagent(middleware: list | None = None):
    """Fab Trace 서브에이전트 SubAgent 딕셔너리 반환"""
    def hitl_description(tool_call, state, runtime):
        return build_hitl_confirm_description(tool_call, state, runtime, domain="fab_trace")

    spec = {
        "name": "analyze-fab-trace",
        "description": "팹 설비 트레이스 데이터를 분석하여 불량 원인을 추적합니다",
        "system_prompt": FAB_TRACE_AGENT_PROMPT,
        "tools": get_fab_trace_tools(),
        "interrupt_on": {
            "get_defect_summary": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_defect_map": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_defects": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_fdc_traceback": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_equipment_health": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_trace_summary": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_param_drift": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_trace_compare": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_equipment_list": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_equipment_detail": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_trace_latest": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_trace_oos": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_trace_data": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_alarms": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_alarm_summary": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_alarm_trend": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_events": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_event_timeline": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
            "get_param_correlation": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": hitl_description,
            },
        },
    }
    if middleware:
        spec["middleware"] = middleware
    return spec

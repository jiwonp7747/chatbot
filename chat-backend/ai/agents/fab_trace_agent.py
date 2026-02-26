"""
Fab Trace 설비 분석 서브에이전트

팹 설비 트레이스 데이터를 분석하여 불량 원인을 추적합니다.
시나리오 1: 불량률 상승 원인 추적 (8개 도구)
"""
import logging

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from ai.agents.base import BaseAgent
from ai.tools.fab_trace import get_fab_trace_tools

logger = logging.getLogger("chat-server")

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

중요 규칙:
- 반드시 데이터에 기반하여 판단하세요. 추측하지 마세요.
- 각 단계의 결과를 요약하고 다음 단계로의 논리적 연결을 설명하세요.
- 최종 결론에는 근본 원인 설비, 파라미터, 권장 조치를 포함하세요.
- 한국어로 응답하세요.
"""


class FabTraceAgent(BaseAgent):

    def __init__(self, model: str):
        super().__init__(model)

    def get_name(self) -> str:
        return "fab_trace_agent"

    def get_description(self) -> str:
        return "팹 설비 트레이스 데이터를 분석하여 불량 원인을 추적합니다"

    def get_system_prompt(self) -> str:
        return FAB_TRACE_AGENT_PROMPT

    def get_tools(self) -> list:
        return get_fab_trace_tools()

    def as_tool(self):
        """Fab Trace 서브에이전트를 analyze_fab_trace 도구로 래핑"""
        agent = self.build()

        @tool
        async def analyze_fab_trace(request: str) -> str:
            """팹 설비 트레이스 데이터를 분석하여 불량 원인을 추적합니다.
            불량률 상승, 수율 하락, 설비 이상 등의 원인을 찾을 때 사용합니다.

            Args:
                request: 분석 요청 (예: "최근 24시간 불량률 상승 원인을 추적해줘", "CVD-A02 설비 상태를 확인해줘")
            """
            logger.info(f"🔍 Fab Trace 서브에이전트 호출: {request[:50]}")
            result = await agent.ainvoke({
                "messages": [HumanMessage(content=request)]
            })
            return self.extract_ai_content(result)

        return analyze_fab_trace

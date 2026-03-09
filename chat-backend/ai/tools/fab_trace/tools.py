"""
Fab Trace API 도구 — 시나리오 1: 불량률 상승 원인 추적

팹 설비 트레이스 데이터 API를 LangChain Tool로 래핑합니다.
에이전트가 불량 발생 → LOT 특정 → 설비 역추적 → 파라미터 drift 분석까지
단계적으로 근본 원인을 추적할 수 있도록 8개 도구를 제공합니다.
"""

import os
import json
from datetime import datetime
from typing import Optional

import httpx
from langchain_core.tools import tool

FAB_TRACE_API_URL = os.getenv("FAB_TRACE_API_URL", "http://localhost:8080")


def _format_response(result: dict, max_rows: int = 20) -> str:
    """API 응답을 에이전트가 읽기 좋은 텍스트로 포맷팅"""
    summary = result.get("summary", "")
    meta = result.get("meta", {})
    data = result.get("data", [])

    parts = []
    if summary:
        parts.append(f"[요약] {summary}")

    if meta:
        total = meta.get("total_count", 0)
        qtime = meta.get("query_time_ms", 0)
        parts.append(f"[메타] 총 {total}건, 조회 {qtime:.0f}ms")

    if isinstance(data, list):
        if len(data) > max_rows:
            parts.append(f"[데이터] 상위 {max_rows}건 (전체 {len(data)}건):")
            parts.append(json.dumps(data[:max_rows], ensure_ascii=False, default=str, indent=2))
        else:
            parts.append(f"[데이터] {len(data)}건:")
            parts.append(json.dumps(data, ensure_ascii=False, default=str, indent=2))
    elif isinstance(data, dict):
        parts.append("[데이터]")
        parts.append(json.dumps(data, ensure_ascii=False, default=str, indent=2))

    return "\n".join(parts)


async def _call_api(path: str, params: dict | None = None) -> str:
    """Fab Trace API 공통 호출"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{FAB_TRACE_API_URL}{path}", params=params)
            response.raise_for_status()
        return _format_response(response.json())

    except httpx.ConnectError:
        return "Fab Trace API 서버에 연결할 수 없습니다."
    except httpx.HTTPStatusError as e:
        return f"API 오류 (HTTP {e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        return f"API 호출 실패: {str(e)}"


# ── 1. 불량 집계 ─────────────────────────────────────────

@tool
async def get_defect_summary(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> str:
    """불량 유형별 집계를 조회합니다. Particle, Scratch, Mura 등 어떤 불량이 얼마나 발생했는지 파악할 때 사용합니다.
    수율 하락 원인 분석의 첫 단계로, 급증한 불량 유형을 식별합니다.

    Args:
        start: 조회 시작 시간 (ISO 8601, 예: 2026-02-26T00:00:00Z). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
    """
    params = {}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    return await _call_api("/api/defects/summary", params)


# ── 2. 불량 좌표 분포 ────────────────────────────────────

@tool
async def get_defect_map(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    defect_type: Optional[str] = None,
    limit: int = 500,
) -> str:
    """기판 위 불량 좌표(x, y) 분포를 조회합니다. 불량이 기판 어느 위치에 집중되는지 패턴을 분석할 때 사용합니다.
    - 엣지(가장자리) 집중 → 척(chuck) 이슈 의심
    - 중앙 집중 → 가스 분배 불균일 의심
    - 랜덤 분포 → 파티클 오염 의심
    - 특정 위치 반복 → 기계적 접촉 불량 의심

    Args:
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        defect_type: 불량 유형 필터 (Particle, Scratch, Mura, Short, Open, Pinhole)
        limit: 최대 반환 건수 (기본 500, 최대 1000)
    """
    params = {"limit": limit}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    if defect_type:
        params["defect_type"] = defect_type
    return await _call_api("/api/defects/map", params)


# ── 3. 불량 목록 ─────────────────────────────────────────

@tool
async def get_defects(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    defect_type: Optional[str] = None,
    lot_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """불량 목록을 조회합니다. 불량이 발생한 LOT ID, 설비, 좌표, 크기 등 상세 정보를 확인할 때 사용합니다.
    어떤 LOT에서 불량이 집중되는지 파악하고, 해당 LOT를 FDC 역추적하는 데 활용합니다.

    Args:
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        defect_type: 불량 유형 필터 (Particle, Scratch, Mura, Short, Open, Pinhole)
        lot_id: LOT ID 필터
        limit: 최대 반환 건수 (기본 50, 최대 1000)
        offset: 페이지 오프셋
    """
    params = {"limit": limit, "offset": offset}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    if defect_type:
        params["defect_type"] = defect_type
    if lot_id:
        params["lot_id"] = lot_id
    return await _call_api("/api/defects", params)


# ── 4. FDC 역추적 ────────────────────────────────────────

@tool
async def get_fdc_traceback(
    lot_id: str,
    limit: int = 500,
) -> str:
    """불량이 발생한 LOT의 설비 트레이스 데이터를 역추적합니다. (FDC: Fault Detection & Classification)
    특정 LOT가 어떤 설비에서 처리되었고, 처리 당시 각 파라미터 값이 어떠했는지 조회합니다.
    Spec 범위(LSL/USL)를 벗어난 파라미터를 자동으로 식별하여 근본 원인 설비와 파라미터를 특정합니다.

    Args:
        lot_id: 역추적할 LOT ID (예: LOT-260226-00412). get_defects 결과에서 확인 가능
        limit: 최대 반환 건수 (기본 500)
    """
    params = {"lot_id": lot_id, "limit": limit}
    return await _call_api("/api/analytics/fdc", params)


# ── 5. 설비 건강도 ───────────────────────────────────────

@tool
async def get_equipment_health(
    equipment_id: str,
    hours: int = 24,
) -> str:
    """특정 설비의 건강도 점수를 조회합니다. 최근 알람 수, CRITICAL/WARNING 비율, OOS(Out-of-Spec) 비율을 기반으로
    0~100점 건강도를 산출합니다.
    - 80점 이상: 양호
    - 60~80점: 주의
    - 60점 미만: 위험 (즉시 점검 필요)

    Args:
        equipment_id: 설비 ID (예: CVD-A01, CVD-A02, ETCH-B01, SPUT-C01 등)
        hours: 조회 시간 범위 (기본 24시간)
    """
    params = {"hours": hours}
    return await _call_api(f"/api/equipment/{equipment_id}/health", params)


# ── 6. 트레이스 통계 요약 ────────────────────────────────

@tool
async def get_trace_summary(
    equipment_id: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    param_name: Optional[str] = None,
) -> str:
    """특정 설비의 파라미터 통계 요약(평균, 표준편차, 최솟값, 최댓값, OOS율)을 조회합니다.
    설비의 공정 안정성을 수치로 판단하고, Spec 대비 여유가 얼마나 있는지 확인할 때 사용합니다.

    Args:
        equipment_id: 설비 ID (예: CVD-A01, ETCH-B01)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        param_name: 특정 파라미터만 조회 (예: temperature, pressure, gas_flow_SiH4)
    """
    params = {}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    if param_name:
        params["param_name"] = param_name
    return await _call_api(f"/api/trace/{equipment_id}/summary", params)


# ── 7. 파라미터 Drift 분석 ───────────────────────────────

@tool
async def get_param_drift(
    equipment_id: str,
    param_name: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    interval: str = "1h",
) -> str:
    """설비 파라미터의 시간에 따른 drift(편차 추이)를 분석합니다.
    이동평균과 전체평균의 차이를 시간대별로 보여주어, 언제부터 파라미터가 이탈하기 시작했는지 파악합니다.
    drift가 감지되면 예방정비(PM) 시점을 판단하는 데 활용됩니다.

    Args:
        equipment_id: 설비 ID (예: CVD-A02)
        param_name: 분석할 파라미터명 (예: temperature, pressure, gas_flow_SiH4)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        interval: 집계 간격 (5m: 5분, 1h: 1시간, 1d: 1일)
    """
    params = {"equipment_id": equipment_id, "param_name": param_name, "interval": interval}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    return await _call_api("/api/analytics/drift", params)


# ── 8. 동일 타입 설비 비교 ───────────────────────────────

@tool
async def get_trace_compare(
    equipment_type: str,
    param_name: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> str:
    """동일 타입 설비 간 특정 파라미터를 비교합니다. 같은 종류 설비(예: CVD 3대) 중 어느 설비만
    이상 값을 보이는지 확인하여 개별 설비 문제인지 전체 라인 문제인지 판별합니다.

    Args:
        equipment_type: 설비 타입 (CVD, Etcher, Sputter, Coater, Exposure, Inspection)
        param_name: 비교할 파라미터명 (예: temperature, pressure)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
    """
    params = {"equipment_type": equipment_type, "param_name": param_name}
    if start:
        params["start"] = start.isoformat()
    if end:
        params["end"] = end.isoformat()
    return await _call_api("/api/trace/compare", params)


# ── 9. 설비 목록 ──────────────────────────────────────────

@tool
async def get_equipment_list() -> str:
    """전체 설비 목록과 현재 상태를 조회합니다. 각 설비의 ID, 타입, 챔버 수, 상태(RUNNING/IDLE/PM)를 확인할 때 사용합니다.
    분석 전 어떤 설비가 있는지 파악하거나, 특정 타입의 설비 ID를 찾을 때 활용합니다."""
    return await _call_api("/api/equipment")


# ── 10. 설비 상세 정보 ────────────────────────────────────

@tool
async def get_equipment_detail(equipment_id: str) -> str:
    """특정 설비의 상세 정보를 조회합니다. 설비 타입, 챔버 수, 설치 위치, 현재 상태, 마지막 PM 일시 등을 확인합니다.

    Args:
        equipment_id: 설비 ID (예: CVD-A01, ETCH-B01)"""
    return await _call_api(f"/api/equipment/{equipment_id}")


# ── 11. 최신 센서 스냅샷 ──────────────────────────────────

@tool
async def get_trace_latest() -> str:
    """모든 설비의 최신 센서 데이터 스냅샷을 조회합니다. 현재 시점의 각 설비별 파라미터 값을 한눈에 확인할 때 사용합니다.
    실시간 모니터링이나 현재 상태 파악에 활용됩니다."""
    return await _call_api("/api/trace/latest")


# ── 12. OOS 데이터 조회 ───────────────────────────────────

@tool
async def get_trace_oos(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    equipment_id: Optional[str] = None,
    param_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Spec 범위(LSL/USL)를 벗어난 OOS(Out-of-Spec) 트레이스 데이터를 조회합니다.
    어떤 설비에서, 어떤 파라미터가, 얼마나 자주 Spec을 이탈하는지 파악할 때 사용합니다.

    Args:
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        equipment_id: 설비 ID 필터 (예: CVD-A01)
        param_name: 파라미터명 필터 (예: temperature)
        limit: 최대 반환 건수 (기본 100)
        offset: 페이지 오프셋"""
    params = {"limit": limit, "offset": offset}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    if equipment_id: params["equipment_id"] = equipment_id
    if param_name: params["param_name"] = param_name
    return await _call_api("/api/trace/oos", params)


# ── 13. 설비 트레이스 데이터 ─────────────────────────────

@tool
async def get_trace_data(
    equipment_id: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    param_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """특정 설비의 원시 트레이스 데이터를 조회합니다. 센서별 실측값, Spec 범위, OOS 여부를 시계열로 확인할 때 사용합니다.
    상세한 시계열 분석이나 특정 시점의 정확한 값을 확인할 때 활용합니다.

    Args:
        equipment_id: 설비 ID (예: CVD-A01, ETCH-B01)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        param_name: 특정 파라미터만 조회 (예: temperature, pressure)
        limit: 최대 반환 건수 (기본 100)
        offset: 페이지 오프셋"""
    params = {"limit": limit, "offset": offset}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    if param_name: params["param_name"] = param_name
    return await _call_api(f"/api/trace/{equipment_id}", params)


# ── 14. 알람 목록 ─────────────────────────────────────────

@tool
async def get_alarms(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    equipment_id: Optional[str] = None,
    alarm_level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """알람 발생 이력을 조회합니다. 설비별, 알람 레벨별로 필터링하여 최근 알람 현황을 파악합니다.
    CRITICAL/WARNING/INFO 레벨로 구분되며, 설비 이상 징후를 조기에 감지할 때 사용합니다.

    Args:
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        equipment_id: 설비 ID 필터 (예: CVD-A01)
        alarm_level: 알람 레벨 필터 (CRITICAL, WARNING, INFO)
        limit: 최대 반환 건수 (기본 100)
        offset: 페이지 오프셋"""
    params = {"limit": limit, "offset": offset}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    if equipment_id: params["equipment_id"] = equipment_id
    if alarm_level: params["alarm_level"] = alarm_level
    return await _call_api("/api/alarms", params)


# ── 15. 알람 집계 ─────────────────────────────────────────

@tool
async def get_alarm_summary(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> str:
    """설비별, 알람 레벨별 알람 발생 건수를 집계합니다. 어떤 설비에서 CRITICAL 알람이 많이 발생했는지
    한눈에 파악할 때 사용합니다. 설비 건강도 분석의 보조 지표로 활용됩니다.

    Args:
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재"""
    params = {}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    return await _call_api("/api/alarms/summary", params)


# ── 16. 알람 추이 ─────────────────────────────────────────

@tool
async def get_alarm_trend(
    equipment_id: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    interval: str = "1h",
) -> str:
    """특정 설비의 알람 발생 추이를 시간대별로 조회합니다. 알람이 특정 시간대에 집중되는지,
    점차 증가하는 추세인지 파악하여 설비 열화나 간헐적 이상을 감지합니다.

    Args:
        equipment_id: 설비 ID (예: CVD-A02, ETCH-B01)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        interval: 집계 간격 (5m: 5분, 1h: 1시간, 1d: 1일)"""
    params = {"interval": interval}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    return await _call_api(f"/api/alarms/{equipment_id}/trend", params)


# ── 17. 이벤트 로그 ───────────────────────────────────────

@tool
async def get_events(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    equipment_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """설비 이벤트 로그를 조회합니다. PM(예방정비), 레시피 변경, 캘리브레이션 등 설비에서 발생한 이벤트를 확인합니다.
    불량 발생 전후에 어떤 이벤트가 있었는지 추적하여 원인 파악에 활용합니다.

    Args:
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        equipment_id: 설비 ID 필터 (예: CVD-A01)
        event_type: 이벤트 유형 필터 (PM, RECIPE_CHANGE, CALIBRATION, CHAMBER_CLEAN, ERROR 등)
        limit: 최대 반환 건수 (기본 100)
        offset: 페이지 오프셋"""
    params = {"limit": limit, "offset": offset}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    if equipment_id: params["equipment_id"] = equipment_id
    if event_type: params["event_type"] = event_type
    return await _call_api("/api/events", params)


# ── 18. 설비 이벤트 타임라인 ─────────────────────────────

@tool
async def get_event_timeline(
    equipment_id: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 100,
) -> str:
    """특정 설비의 이벤트를 시간순으로 조회합니다. PM, 레시피 변경, 오류 등 이벤트 이력을 타임라인으로 확인하여
    설비 상태 변화의 인과관계를 분석합니다.

    Args:
        equipment_id: 설비 ID (예: CVD-A01, ETCH-B01)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재
        limit: 최대 반환 건수 (기본 100)"""
    params = {"limit": limit}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    return await _call_api(f"/api/events/{equipment_id}/timeline", params)


# ── 19. 파라미터 상관관계 분석 ───────────────────────────

@tool
async def get_param_correlation(
    equipment_id: str,
    param_x: str,
    param_y: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> str:
    """두 파라미터 간 상관관계(Pearson 상관계수)를 분석합니다. 예를 들어 온도와 압력이 함께 변하는지,
    가스 유량 변화가 증착 두께에 영향을 주는지 등을 정량적으로 확인합니다.
    - 상관계수 0.7 이상: 강한 양의 상관
    - 상관계수 -0.7 이하: 강한 음의 상관
    - 상관계수 -0.3~0.3: 상관 없음

    Args:
        equipment_id: 설비 ID (예: CVD-A01)
        param_x: 첫 번째 파라미터명 (예: temperature)
        param_y: 두 번째 파라미터명 (예: pressure)
        start: 조회 시작 시간 (ISO 8601). 미입력시 최근 24시간
        end: 조회 종료 시간 (ISO 8601). 미입력시 현재"""
    params = {"equipment_id": equipment_id, "param_x": param_x, "param_y": param_y}
    if start: params["start"] = start.isoformat()
    if end: params["end"] = end.isoformat()
    return await _call_api("/api/analytics/correlation", params)

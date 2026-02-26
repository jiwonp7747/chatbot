from .tools import (
    get_defect_summary,
    get_defect_map,
    get_defects,
    get_fdc_traceback,
    get_equipment_health,
    get_trace_summary,
    get_param_drift,
    get_trace_compare,
)


def get_fab_trace_tools() -> list:
    """Fab Trace 시나리오 1 (불량률 상승 원인 추적) 도구 목록 반환"""
    return [
        get_defect_summary,
        get_defect_map,
        get_defects,
        get_fdc_traceback,
        get_equipment_health,
        get_trace_summary,
        get_param_drift,
        get_trace_compare,
    ]

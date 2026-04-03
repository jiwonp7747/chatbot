package ai.bistelligence.chat_backend_spring.aiagent.tool.fabtrace;

import lombok.RequiredArgsConstructor;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class FabTraceTools {

    private final FabTraceApiClient apiClient;

    // ───────────────────────────── 1. getDefectSummary ─────────────────────────────

    @Tool(description = "결함 유형별 집계 조회 - Particle, Scratch, Mura, Short, Open, Pinhole. 특정 결함 유형이 급증했는지 확인하는 첫 단계.")
    public String getDefectSummary(
            @ToolParam(description = "조회 시작 시간 (ISO 8601), 기본값: 최근 24시간", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601), 기본값: 현재", required = false) String end) {
        return apiClient.get("/api/defects/summary",
                FabTraceApiClient.params("start", start, "end", end));
    }

    // ───────────────────────────── 2. getDefectMap ─────────────────────────────────

    @Tool(description = "결함 좌표 분포 조회 - 웨이퍼 위의 결함 (x,y) 좌표 분포. Edge집중->Chuck문제, Center집중->가스 분배 불균형, Random->파티클 오염, 반복위치->기계적 접촉 결함")
    public String getDefectMap(
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "결함 유형 필터 (Particle, Scratch, Mura, Short, Open, Pinhole)", required = false) String defectType,
            @ToolParam(description = "최대 반환 건수, 기본값 500, 최대 1000", required = false) Integer limit) {
        return apiClient.get("/api/defects/map",
                FabTraceApiClient.params("start", start, "end", end,
                        "defect_type", defectType, "limit", limit));
    }

    // ───────────────────────────── 3. getDefects ──────────────────────────────────

    @Tool(description = "결함 상세 목록 조회 - LOT ID, 장비, 좌표, 크기 포함. 결함이 집중된 LOT를 식별하여 FDC 추적에 활용.")
    public String getDefects(
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "결함 유형 필터 (Particle, Scratch, Mura, Short, Open, Pinhole)", required = false) String defectType,
            @ToolParam(description = "LOT ID 필터", required = false) String lotId,
            @ToolParam(description = "최대 반환 건수, 기본값 50, 최대 1000", required = false) Integer limit,
            @ToolParam(description = "페이지네이션 오프셋, 기본값 0", required = false) Integer offset) {
        return apiClient.get("/api/defects",
                FabTraceApiClient.params("start", start, "end", end,
                        "defect_type", defectType, "lot_id", lotId,
                        "limit", limit, "offset", offset));
    }

    // ───────────────────────────── 4. getFdcTraceback ─────────────────────────────

    @Tool(description = "FDC 역추적 - 불량 LOT의 장비 가공 이력 추적. Spec(LSL/USL) 초과 파라미터를 자동 식별하여 원인 장비와 파라미터를 특정.")
    public String getFdcTraceback(
            @ToolParam(description = "추적할 LOT ID (예: LOT-260226-00412)") String lotId,
            @ToolParam(description = "최대 반환 건수, 기본값 500", required = false) Integer limit) {
        return apiClient.get("/api/analytics/fdc",
                FabTraceApiClient.params("lot_id", lotId, "limit", limit));
    }

    // ───────────────────────────── 5. getEquipmentHealth ──────────────────────────

    @Tool(description = "장비 건강 점수 조회 (0-100) - 최근 알람, CRITICAL/WARNING 비율, OOS 비율 기반. 80+: 정상, 60-80: 주의, 60미만: 즉시 점검 필요")
    public String getEquipmentHealth(
            @ToolParam(description = "장비 ID (CVD-A01, CVD-A02, ETCH-B01, SPUT-C01 등)") String equipmentId,
            @ToolParam(description = "조회 기간(시간), 기본값 24", required = false) Integer hours) {
        return apiClient.get("/api/equipment/" + equipmentId + "/health",
                FabTraceApiClient.params("hours", hours));
    }

    // ───────────────────────────── 6. getTraceSummary ─────────────────────────────

    @Tool(description = "장비 파라미터 통계 조회 - 평균, 표준편차, 최소, 최대, OOS율. 공정 안정성과 Spec 마진 평가.")
    public String getTraceSummary(
            @ToolParam(description = "장비 ID") String equipmentId,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "파라미터명 (temperature, pressure, gas_flow_SiH4 등)", required = false) String paramName) {
        return apiClient.get("/api/trace/" + equipmentId + "/summary",
                FabTraceApiClient.params("start", start, "end", end,
                        "param_name", paramName));
    }

    // ───────────────────────────── 7. getParamDrift ───────────────────────────────

    @Tool(description = "파라미터 드리프트 분석 - 시간대별 이동평균 vs 전체평균. 파라미터가 서서히 벗어나는 시점 감지, PM 시기 판단에 활용.")
    public String getParamDrift(
            @ToolParam(description = "장비 ID") String equipmentId,
            @ToolParam(description = "파라미터명 (temperature, pressure, gas_flow_SiH4 등)") String paramName,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "집계 구간 (5m, 1h, 1d), 기본값 1h", required = false) String interval) {
        return apiClient.get("/api/analytics/drift",
                FabTraceApiClient.params("equipment_id", equipmentId,
                        "param_name", paramName, "start", start,
                        "end", end, "interval", interval));
    }

    // ───────────────────────────── 8. getTraceCompare ─────────────────────────────

    @Tool(description = "동일 유형 장비 간 파라미터 비교 - 같은 유형 장비의 동일 파라미터를 비교하여 개별 장비 이상 vs 라인 전체 문제를 구분.")
    public String getTraceCompare(
            @ToolParam(description = "장비 유형 (CVD, Etcher, Sputter, Coater, Exposure, Inspection)") String equipmentType,
            @ToolParam(description = "비교할 파라미터명") String paramName,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end) {
        return apiClient.get("/api/trace/compare",
                FabTraceApiClient.params("equipment_type", equipmentType,
                        "param_name", paramName, "start", start, "end", end));
    }

    // ───────────────────────────── 9. getEquipmentList ────────────────────────────

    @Tool(description = "전체 장비 목록 조회 - ID, 유형, 챔버 수, 상태(RUNNING/IDLE/PM). 사용 가능한 장비 ID 확인이나 특정 유형 장비 검색에 활용.")
    public String getEquipmentList() {
        return apiClient.get("/api/equipment", FabTraceApiClient.params());
    }

    // ───────────────────────────── 10. getEquipmentDetail ─────────────────────────

    @Tool(description = "장비 상세 정보 조회 - 유형, 챔버 수, 위치, 상태, 마지막 PM 시점.")
    public String getEquipmentDetail(
            @ToolParam(description = "장비 ID") String equipmentId) {
        return apiClient.get("/api/equipment/" + equipmentId,
                FabTraceApiClient.params());
    }

    // ───────────────────────────── 11. getTraceLatest ─────────────────────────────

    @Tool(description = "전체 장비 최신 센서 데이터 스냅샷 조회 - 실시간 파라미터 모니터링 및 현재 상태 확인.")
    public String getTraceLatest() {
        return apiClient.get("/api/trace/latest", FabTraceApiClient.params());
    }

    // ───────────────────────────── 12. getTraceOos ────────────────────────────────

    @Tool(description = "Spec 초과(OOS) 트레이스 데이터 조회 - 어떤 장비/파라미터가 LSL/USL을 초과했는지와 빈도 확인.")
    public String getTraceOos(
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "장비 ID 필터", required = false) String equipmentId,
            @ToolParam(description = "파라미터명 필터", required = false) String paramName,
            @ToolParam(description = "최대 반환 건수, 기본값 100", required = false) Integer limit,
            @ToolParam(description = "페이지네이션 오프셋, 기본값 0", required = false) Integer offset) {
        return apiClient.get("/api/trace/oos",
                FabTraceApiClient.params("start", start, "end", end,
                        "equipment_id", equipmentId, "param_name", paramName,
                        "limit", limit, "offset", offset));
    }

    // ───────────────────────────── 13. getTraceData ───────────────────────────────

    @Tool(description = "장비 원시 트레이스 데이터 조회 - 센서값, Spec 범위, OOS 여부 포함 시계열 데이터.")
    public String getTraceData(
            @ToolParam(description = "장비 ID") String equipmentId,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "파라미터명 필터", required = false) String paramName,
            @ToolParam(description = "최대 반환 건수, 기본값 100", required = false) Integer limit,
            @ToolParam(description = "페이지네이션 오프셋, 기본값 0", required = false) Integer offset) {
        return apiClient.get("/api/trace/" + equipmentId,
                FabTraceApiClient.params("start", start, "end", end,
                        "param_name", paramName, "limit", limit, "offset", offset));
    }

    // ───────────────────────────── 14. getAlarms ──────────────────────────────────

    @Tool(description = "알람 이력 조회 - CRITICAL/WARNING/INFO 수준별 필터링. 장비 이상을 조기 감지.")
    public String getAlarms(
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "장비 ID 필터", required = false) String equipmentId,
            @ToolParam(description = "알람 레벨 (CRITICAL, WARNING, INFO)", required = false) String alarmLevel,
            @ToolParam(description = "최대 반환 건수, 기본값 100", required = false) Integer limit,
            @ToolParam(description = "페이지네이션 오프셋, 기본값 0", required = false) Integer offset) {
        return apiClient.get("/api/alarms",
                FabTraceApiClient.params("start", start, "end", end,
                        "equipment_id", equipmentId, "alarm_level", alarmLevel,
                        "limit", limit, "offset", offset));
    }

    // ───────────────────────────── 15. getAlarmSummary ────────────────────────────

    @Tool(description = "장비별 알람 집계 조회 - 장비별, 레벨별 알람 건수. CRITICAL 알람이 많은 장비를 빠르게 파악.")
    public String getAlarmSummary(
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end) {
        return apiClient.get("/api/alarms/summary",
                FabTraceApiClient.params("start", start, "end", end));
    }

    // ───────────────────────────── 16. getAlarmTrend ──────────────────────────────

    @Tool(description = "알람 트렌드 조회 - 시간대별 알람 빈도. 특정 시간대 집중 여부나 증가 추세를 파악하여 점진적 열화 감지.")
    public String getAlarmTrend(
            @ToolParam(description = "장비 ID") String equipmentId,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "집계 구간 (5m, 1h, 1d), 기본값 1h", required = false) String interval) {
        return apiClient.get("/api/alarms/" + equipmentId + "/trend",
                FabTraceApiClient.params("start", start, "end", end,
                        "interval", interval));
    }

    // ───────────────────────────── 17. getEvents ──────────────────────────────────

    @Tool(description = "장비 이벤트 로그 조회 - PM, 레시피 변경, 캘리브레이션 등. 결함 발생 전후 이벤트를 추적하여 인과관계 분석.")
    public String getEvents(
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "장비 ID 필터", required = false) String equipmentId,
            @ToolParam(description = "이벤트 유형 (PM, RECIPE_CHANGE, CALIBRATION, CHAMBER_CLEAN, ERROR 등)", required = false) String eventType,
            @ToolParam(description = "최대 반환 건수, 기본값 100", required = false) Integer limit,
            @ToolParam(description = "페이지네이션 오프셋, 기본값 0", required = false) Integer offset) {
        return apiClient.get("/api/events",
                FabTraceApiClient.params("start", start, "end", end,
                        "equipment_id", equipmentId, "event_type", eventType,
                        "limit", limit, "offset", offset));
    }

    // ───────────────────────────── 18. getEventTimeline ───────────────────────────

    @Tool(description = "장비 이벤트 타임라인 조회 - 시간순 이벤트 이력. PM/레시피/에러 시퀀스로 상태 변화 인과관계 분석.")
    public String getEventTimeline(
            @ToolParam(description = "장비 ID") String equipmentId,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end,
            @ToolParam(description = "최대 반환 건수, 기본값 100", required = false) Integer limit) {
        return apiClient.get("/api/events/" + equipmentId + "/timeline",
                FabTraceApiClient.params("start", start, "end", end,
                        "limit", limit));
    }

    // ───────────────────────────── 19. getParamCorrelation ────────────────────────

    @Tool(description = "파라미터 간 상관관계 분석 - 피어슨 상관계수. >=0.7: 강한 양의 상관, <=-0.7: 강한 음의 상관, -0.3~0.3: 상관없음")
    public String getParamCorrelation(
            @ToolParam(description = "장비 ID") String equipmentId,
            @ToolParam(description = "첫 번째 파라미터명") String paramX,
            @ToolParam(description = "두 번째 파라미터명") String paramY,
            @ToolParam(description = "조회 시작 시간 (ISO 8601)", required = false) String start,
            @ToolParam(description = "조회 종료 시간 (ISO 8601)", required = false) String end) {
        return apiClient.get("/api/analytics/correlation",
                FabTraceApiClient.params("equipment_id", equipmentId,
                        "param_x", paramX, "param_y", paramY,
                        "start", start, "end", end));
    }
}

-- =============================================================================
-- Fab Trace API - Equipment(설비) 쿼리
-- 테이블: equipment, event_log, alarm_log, trace_data
-- 라우터: routers/equipment.py
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GET /api/equipment
-- 전체 설비 목록 + 상태 조회
-- equipment 테이블에서 전체 설비를 조회한 후,
-- 각 설비의 최신 이벤트를 기반으로 상태(RUNNING/PM/IDLE) 결정
-- -----------------------------------------------------------------------------

-- 1) 전체 설비 목록
SELECT *
FROM equipment
ORDER BY equipment_id;

-- 2) 각 설비의 최신 이벤트로 상태 판단
--    PM_START → PM, IDLE → IDLE, 그 외 → RUNNING
SELECT event_type
FROM event_log
WHERE equipment_id = $1
ORDER BY occurred_at DESC
LIMIT 1;


-- -----------------------------------------------------------------------------
-- GET /api/equipment/{equipment_id}
-- 특정 설비 상세 정보 조회
-- 파라미터: equipment_id
-- -----------------------------------------------------------------------------
SELECT *
FROM equipment
WHERE equipment_id = $1;


-- -----------------------------------------------------------------------------
-- GET /api/equipment/{equipment_id}/health
-- 설비 건강도 점수 산출
-- 최근 N시간 내 알람 건수(CRITICAL/WARNING)와 OOS 비율을 기반으로
-- 건강도 점수를 계산: 100 - (CRITICAL * 5) - (WARNING * 1) - (OOS비율 * 2)
-- 파라미터: equipment_id, hours(기본 24시간)
-- -----------------------------------------------------------------------------

-- 1) 설비 존재 확인
SELECT equipment_id
FROM equipment
WHERE equipment_id = $1;

-- 2) 알람 건수 집계 (CRITICAL, WARNING 분리 카운트)
--    FILTER 구문으로 레벨별 분리 집계
SELECT
    count(*)                                        AS total,
    count(*) FILTER (WHERE alarm_level = 'CRITICAL') AS critical,
    count(*) FILTER (WHERE alarm_level = 'WARNING')  AS warning
FROM alarm_log
WHERE equipment_id = $1
  AND occurred_at >= $2;

-- 3) OOS(규격 이탈) 비율 산출
--    전체 센서값 중 spec 범위 밖인 건수의 비율
SELECT
    count(*)                                                              AS total,
    count(*) FILTER (WHERE param_value < spec_lsl OR param_value > spec_usl) AS oos
FROM trace_data
WHERE equipment_id = $1
  AND collected_at >= $2;

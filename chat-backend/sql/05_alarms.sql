-- =============================================================================
-- Fab Trace API - Alarm(알람) 쿼리
-- 테이블: alarm_log
-- 라우터: routers/alarms.py
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GET /api/alarms
-- 알람 목록 조회 (설비, 레벨, 시간 필터)
-- 발생 시간 역순 정렬, 페이지네이션 지원
-- 선택적 필터: equipment_id, alarm_level
-- 파라미터: start, end, [equipment_id], [alarm_level], limit, offset
-- -----------------------------------------------------------------------------

-- 1) 총 건수 카운트
SELECT count(*)
FROM alarm_log
WHERE occurred_at BETWEEN $1 AND $2
  -- [선택] AND equipment_id = $3
  -- [선택] AND alarm_level = $4
;

-- 2) 알람 목록 (페이지네이션)
SELECT
    equipment_id,
    alarm_code,
    alarm_level,
    param_name,
    threshold_value,
    actual_value,
    occurred_at
FROM alarm_log
WHERE occurred_at BETWEEN $1 AND $2
  -- [선택] AND equipment_id = $3
  -- [선택] AND alarm_level = $4
ORDER BY occurred_at DESC
LIMIT $n OFFSET $m;


-- -----------------------------------------------------------------------------
-- GET /api/alarms/summary
-- 설비별/레벨별 알람 집계
-- equipment_id + alarm_level 조합별 발생 건수를 집계
-- 건수 내림차순 정렬
-- 파라미터: start, end
-- -----------------------------------------------------------------------------
SELECT
    equipment_id,
    alarm_level,
    count(*) AS count
FROM alarm_log
WHERE occurred_at BETWEEN $1 AND $2
GROUP BY equipment_id, alarm_level
ORDER BY count DESC;


-- -----------------------------------------------------------------------------
-- GET /api/alarms/{equip_id}/trend
-- 특정 설비의 알람 발생 추이
-- TimescaleDB time_bucket()으로 시간 버킷별 알람 레벨별 건수를 집계
-- 시계열 차트용 데이터
-- 파라미터: equip_id, start, end, interval(5m/1h/1d)
-- -----------------------------------------------------------------------------
SELECT
    time_bucket('1 hour', occurred_at) AS bucket,
    alarm_level,
    count(*)                           AS count
FROM alarm_log
WHERE equipment_id = $1
  AND occurred_at BETWEEN $2 AND $3
GROUP BY bucket, alarm_level
ORDER BY bucket;

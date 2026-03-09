-- =============================================================================
-- Fab Trace API - Analytics(분석) 쿼리
-- 테이블: trace_data
-- 라우터: routers/analytics.py
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GET /api/analytics/drift
-- 파라미터 Drift(경향 변화) 감지
-- 특정 설비/파라미터의 이동평균을 시간 버킷별로 계산하여
-- 전체 평균 대비 drift 비율(%)을 산출
-- TimescaleDB의 time_bucket() 함수 사용 (간격: 5m, 1h, 1d)
-- 파라미터: equipment_id, param_name, start, end, interval
-- -----------------------------------------------------------------------------

-- 1) 기간 전체 평균 계산
SELECT avg(param_value)
FROM trace_data
WHERE equipment_id = $1
  AND param_name = $2
  AND collected_at BETWEEN $3 AND $4;

-- 2) 시간 버킷별 이동평균 (TimescaleDB time_bucket)
--    interval: '5 minutes' | '1 hour' | '1 day'
SELECT
    time_bucket('1 hour', collected_at) AS bucket,
    avg(param_value)                    AS moving_avg
FROM trace_data
WHERE equipment_id = $1
  AND param_name = $2
  AND collected_at BETWEEN $3 AND $4
GROUP BY bucket
ORDER BY bucket;


-- -----------------------------------------------------------------------------
-- GET /api/analytics/correlation
-- 파라미터 간 상관관계 분석 (피어슨 상관계수)
-- 동일 설비/챔버/시간에 수집된 두 파라미터의 상관계수를 계산
-- corr() 집계 함수(PostgreSQL 내장)로 피어슨 상관계수 산출
-- 파라미터: equipment_id, param_x, param_y, start, end
-- -----------------------------------------------------------------------------
SELECT
    corr(a.param_value, b.param_value) AS correlation,
    count(*)                           AS sample_count
FROM trace_data a
JOIN trace_data b
  ON a.equipment_id = b.equipment_id
  AND a.chamber_id = b.chamber_id
  AND a.collected_at = b.collected_at
WHERE a.equipment_id = $1
  AND a.param_name = $2
  AND b.param_name = $3
  AND a.collected_at BETWEEN $4 AND $5;


-- -----------------------------------------------------------------------------
-- GET /api/analytics/fdc
-- FDC(Fault Detection & Classification) 역추적
-- 불량이 발생한 LOT ID로 해당 LOT이 거쳐간 설비의 센서 트레이스를 역추적
-- 시간순 정렬로 공정 이력을 추적할 수 있음
-- 파라미터: lot_id, limit
-- -----------------------------------------------------------------------------
SELECT
    t.lot_id,
    t.equipment_id,
    t.param_name,
    t.param_value,
    t.spec_lsl,
    t.spec_usl,
    t.collected_at
FROM trace_data t
WHERE t.lot_id = $1
ORDER BY t.collected_at
LIMIT $2;

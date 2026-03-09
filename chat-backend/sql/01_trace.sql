-- =============================================================================
-- Fab Trace API - Trace Data 쿼리
-- 테이블: trace_data
-- 라우터: routers/trace.py
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GET /api/trace/latest
-- 전 설비 최신 센서값 스냅샷
-- 각 설비/챔버/파라미터 조합별 가장 최근 수집된 센서값 1건씩 조회
-- DISTINCT ON으로 그룹별 최신 row만 반환
-- -----------------------------------------------------------------------------
SELECT DISTINCT ON (equipment_id, chamber_id, param_name)
    equipment_id,
    chamber_id,
    lot_id,
    glass_id,
    param_name,
    param_value,
    unit,
    spec_lsl,
    spec_usl,
    collected_at
FROM trace_data
ORDER BY equipment_id, chamber_id, param_name, collected_at DESC;


-- -----------------------------------------------------------------------------
-- GET /api/trace/compare
-- 동일 타입 설비 간 파라미터 비교
-- 같은 equipment_type의 설비들을 대상으로 특정 파라미터의 통계값(avg, std, min, max)을
-- 설비별로 집계하여 비교
-- 파라미터: equipment_type, param_name, start, end
-- -----------------------------------------------------------------------------
SELECT
    t.equipment_id,
    avg(t.param_value)    AS avg,
    stddev(t.param_value) AS std,
    min(t.param_value)    AS min_val,
    max(t.param_value)    AS max_val,
    count(*)              AS sample_count
FROM trace_data t
JOIN equipment e ON t.equipment_id = e.equipment_id
WHERE e.equipment_type = $1
  AND t.param_name = $2
  AND t.collected_at BETWEEN $3 AND $4
GROUP BY t.equipment_id
ORDER BY avg DESC;


-- -----------------------------------------------------------------------------
-- GET /api/trace/oos
-- Out-of-Spec(규격 이탈) 데이터 조회
-- spec_lsl(하한) 미만 또는 spec_usl(상한) 초과인 센서값만 필터링
-- 선택적 필터: equipment_id, param_name
-- -----------------------------------------------------------------------------

-- 1) 총 건수 카운트
SELECT count(*)
FROM trace_data
WHERE collected_at BETWEEN $1 AND $2
  AND (param_value < spec_lsl OR param_value > spec_usl)
  -- [선택] AND equipment_id = $3
  -- [선택] AND param_name = $4
;

-- 2) OOS 데이터 목록 (페이지네이션)
SELECT
    equipment_id,
    chamber_id,
    lot_id,
    glass_id,
    param_name,
    param_value,
    unit,
    spec_lsl,
    spec_usl,
    collected_at
FROM trace_data
WHERE collected_at BETWEEN $1 AND $2
  AND (param_value < spec_lsl OR param_value > spec_usl)
  -- [선택] AND equipment_id = $3
  -- [선택] AND param_name = $4
ORDER BY collected_at DESC
LIMIT $n OFFSET $m;


-- -----------------------------------------------------------------------------
-- GET /api/trace/{equip_id}/summary
-- 특정 설비의 파라미터별 통계 요약
-- avg, std, min, max, OOS 건수/비율을 파라미터별로 집계
-- FILTER 구문으로 OOS 건수를 별도 카운트
-- 파라미터: equip_id, start, end, [param_name]
-- -----------------------------------------------------------------------------
SELECT
    equipment_id,
    param_name,
    min(unit)          AS unit,
    avg(param_value)   AS avg,
    stddev(param_value) AS std,
    min(param_value)   AS min_val,
    max(param_value)   AS max_val,
    count(*) FILTER (WHERE param_value < spec_lsl OR param_value > spec_usl) AS oos_count,
    count(*)           AS total_count,
    min(spec_lsl)      AS spec_lsl,
    min(spec_usl)      AS spec_usl
FROM trace_data
WHERE equipment_id = $1
  AND collected_at BETWEEN $2 AND $3
  -- [선택] AND param_name = $4
GROUP BY equipment_id, param_name
ORDER BY param_name;


-- -----------------------------------------------------------------------------
-- GET /api/trace/{equip_id}
-- 특정 설비 트레이스 데이터 조회 (시간, 파라미터 필터)
-- 센서 원본 데이터를 시간순 역순으로 페이지네이션 조회
-- 파라미터: equip_id, start, end, [param_name], limit, offset
-- -----------------------------------------------------------------------------

-- 1) 총 건수 카운트
SELECT count(*)
FROM trace_data
WHERE equipment_id = $1
  AND collected_at BETWEEN $2 AND $3
  -- [선택] AND param_name = $4
;

-- 2) 트레이스 데이터 목록 (페이지네이션)
SELECT
    equipment_id,
    chamber_id,
    lot_id,
    glass_id,
    param_name,
    param_value,
    unit,
    spec_lsl,
    spec_usl,
    collected_at
FROM trace_data
WHERE equipment_id = $1
  AND collected_at BETWEEN $2 AND $3
  -- [선택] AND param_name = $4
ORDER BY collected_at DESC
LIMIT $n OFFSET $m;

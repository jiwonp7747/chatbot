-- =============================================================================
-- Fab Trace API - Defect(불량) 쿼리
-- 테이블: defect
-- 라우터: routers/defects.py
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GET /api/defects
-- 불량 목록 조회 (타입, LOT, 시간 필터)
-- 검출 시간 기준 역순 정렬, 페이지네이션 지원
-- 선택적 필터: defect_type, lot_id
-- 파라미터: start, end, [defect_type], [lot_id], limit, offset
-- -----------------------------------------------------------------------------

-- 1) 총 건수 카운트
SELECT count(*)
FROM defect
WHERE detected_at BETWEEN $1 AND $2
  -- [선택] AND defect_type = $3
  -- [선택] AND lot_id = $4
;

-- 2) 불량 목록 (페이지네이션)
SELECT
    lot_id,
    glass_id,
    inspection_equip_id,
    defect_type,
    defect_code,
    position_x,
    position_y,
    defect_size,
    detected_at
FROM defect
WHERE detected_at BETWEEN $1 AND $2
  -- [선택] AND defect_type = $3
  -- [선택] AND lot_id = $4
ORDER BY detected_at DESC
LIMIT $n OFFSET $m;


-- -----------------------------------------------------------------------------
-- GET /api/defects/summary
-- 불량 유형별 집계
-- 기간 내 defect_type별 발생 건수와 평균 불량 크기를 집계
-- 건수 내림차순 정렬
-- 파라미터: start, end
-- -----------------------------------------------------------------------------
SELECT
    defect_type,
    count(*)          AS count,
    avg(defect_size)  AS avg_size
FROM defect
WHERE detected_at BETWEEN $1 AND $2
GROUP BY defect_type
ORDER BY count DESC;


-- -----------------------------------------------------------------------------
-- GET /api/defects/map
-- 기판 위 불량 좌표 분포 (Defect Map)
-- position_x, position_y 좌표를 포함한 불량 데이터를 반환
-- 프론트엔드에서 기판 위에 불량 위치를 시각화하는 용도
-- 선택적 필터: defect_type
-- 파라미터: start, end, [defect_type], limit
-- -----------------------------------------------------------------------------
SELECT
    lot_id,
    glass_id,
    defect_type,
    defect_code,
    position_x,
    position_y,
    defect_size,
    detected_at
FROM defect
WHERE detected_at BETWEEN $1 AND $2
  -- [선택] AND defect_type = $3
ORDER BY detected_at DESC
LIMIT $n;

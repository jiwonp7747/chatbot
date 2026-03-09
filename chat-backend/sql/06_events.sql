-- =============================================================================
-- Fab Trace API - Event(이벤트) 쿼리
-- 테이블: event_log
-- 라우터: routers/events.py
-- =============================================================================

-- -----------------------------------------------------------------------------
-- GET /api/events
-- 이벤트 로그 조회
-- 설비 라이프사이클 이벤트(LOT_START, PM_START, IDLE 등) 조회
-- 발생 시간 역순 정렬, 페이지네이션 지원
-- 선택적 필터: equipment_id, event_type
-- 파라미터: start, end, [equipment_id], [event_type], limit, offset
-- -----------------------------------------------------------------------------

-- 1) 총 건수 카운트
SELECT count(*)
FROM event_log
WHERE occurred_at BETWEEN $1 AND $2
  -- [선택] AND equipment_id = $3
  -- [선택] AND event_type = $4
;

-- 2) 이벤트 목록 (페이지네이션)
SELECT
    equipment_id,
    event_type,
    event_code,
    lot_id,
    description,
    occurred_at
FROM event_log
WHERE occurred_at BETWEEN $1 AND $2
  -- [선택] AND equipment_id = $3
  -- [선택] AND event_type = $4
ORDER BY occurred_at DESC
LIMIT $n OFFSET $m;


-- -----------------------------------------------------------------------------
-- GET /api/events/{equip_id}/timeline
-- 특정 설비의 이벤트 타임라인
-- 설비별 이벤트를 시간 역순으로 조회하여 타임라인 시각화용 데이터 제공
-- 파라미터: equip_id, start, end, limit
-- -----------------------------------------------------------------------------
SELECT
    equipment_id,
    event_type,
    event_code,
    lot_id,
    description,
    occurred_at
FROM event_log
WHERE equipment_id = $1
  AND occurred_at BETWEEN $2 AND $3
ORDER BY occurred_at DESC
LIMIT $4;

-- count_events.sql: how many events reached the lake in a server_ts window.
-- Owner: M5 · Tracker: M5-03 · Used by: S4 (stored vs accepted), I6 (cold path works)
-- Spec: CONTEXT §7.5 ("lost event"), §9 (lake layout), §14 S4
--
-- Parameters, in order:
--   1. dt_from   varchar 'YYYY-MM-DD'  first dt partition to scan: the UTC date of start_ms
--   2. dt_to     varchar 'YYYY-MM-DD'  last dt partition to scan: the UTC date AFTER end_ms,
--                                      because dt is Firehose's arrival time and an event
--                                      just before midnight can land in the next day
--   3. start_ms  bigint                window start, inclusive (server_ts >= start_ms)
--   4. end_ms    bigint                window end, exclusive (server_ts < end_ms)
--
-- Output, one row:
--   total_rows       every row in the window, duplicates included
--   distinct_events  distinct event_id: the "stored" count that S4 compares with "accepted"
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT event_id) AS distinct_events
FROM events
WHERE dt BETWEEN ? AND ?
  AND server_ts >= ?
  AND server_ts < ?

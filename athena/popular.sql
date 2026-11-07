-- popular.sql: the 20 most-played episodes in a server_ts window, for the POPULAR item.
-- Owner: M5 · Tracker: M5-03 · Used by: recs job (M5-05) -> POPULAR -> /home fallback row
-- Spec: CONTEXT §7.4 rule 3, §8.1 (Popular), §10 ("top 20 episodes by distinct play events,
-- last 7 days"). The job passes a 7-day window.
--
-- Parameters, in order:
--   1. dt_from   varchar 'YYYY-MM-DD'  first dt partition to scan: the UTC date of start_ms
--   2. dt_to     varchar 'YYYY-MM-DD'  last dt partition to scan: the UTC date AFTER end_ms
--                                      (dt is arrival time; late events land a day later)
--   3. start_ms  bigint                window start, inclusive (server_ts >= start_ms)
--   4. end_ms    bigint                window end, exclusive (server_ts < end_ms)
--
-- Output, at most 20 rows, most played first (ties: lower episode_id first):
--   show_id     the episode's show
--   episode_id
--   plays       distinct play events (duplicates in the lake count once)
SELECT
    show_id,
    episode_id,
    COUNT(DISTINCT event_id) AS plays
FROM events
WHERE dt BETWEEN ? AND ?
  AND server_ts >= ?
  AND server_ts < ?
  AND event_type = 'play'
GROUP BY show_id, episode_id
ORDER BY plays DESC, episode_id
LIMIT 20

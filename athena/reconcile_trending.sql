-- reconcile_trending.sql: distinct plays per episode for one UTC day: the cold-path side of S5.
-- Owner: M5 · Tracker: M5-03 · Used by: S5 reconciliation script (M5-06), which compares each
-- row with M4's DynamoDB counter TREND#<day> / EP#<episode_id>.
-- Spec: CONTEXT §6 ("Trending counts distinct play events (by event_id) per UTC date of
-- server_ts"), §8.1 (Trending counter), §14 S5
--
-- Parameters, in order (one UTC day D):
--   1. dt_from   varchar 'YYYY-MM-DD'  D
--   2. dt_to     varchar 'YYYY-MM-DD'  the day after D: plays just before midnight can land there
--   3. start_ms  bigint                D 00:00 UTC, inclusive
--   4. end_ms    bigint                the next day 00:00 UTC, exclusive
--
-- Output, one row per episode with at least one play that day, by episode_id:
--   show_id
--   episode_id
--   plays       distinct play events: must match the counter's "plays" within 1 %
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
ORDER BY episode_id

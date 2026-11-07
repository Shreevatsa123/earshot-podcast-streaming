-- recs.sql: "Because you listened to X" recommendations from co-listening.
-- Owner: M5 · Tracker: M5-03 · Used by: recs job (M5-05) -> recs writer (M5-04) -> RECS items
-- Spec: CONTEXT §8.1 (Recs), §10 (algorithm). The job passes a 30-day window.
--
-- Parameters, in order:
--   1. dt_from   varchar 'YYYY-MM-DD'  first dt partition to scan: the UTC date of start_ms
--   2. dt_to     varchar 'YYYY-MM-DD'  last dt partition to scan: the UTC date AFTER end_ms
--                                      (dt is arrival time; late events land a day later)
--   3. start_ms  bigint                window start, inclusive (server_ts >= start_ms)
--   4. end_ms    bigint                window end, exclusive (server_ts < end_ms)
--
-- Algorithm (§10), over play events in the window:
--   1. who played what: one row per (user, episode), with when they last played it
--   2. eligible users: at least 3 distinct episodes
--   3. seeds: each eligible user's 2 most recently played episodes (ties: lower episode_id)
--   4. co-listening: for each seed episode, how many USERS played both it and each other
--      episode (replays and duplicate events don't inflate it)
--   5. picks: per (user, seed), the top 10 co-played episodes the user hasn't played
--      (ties: lower episode_id)
--   6. filler: if fewer than 10, the most-played episodes (distinct play events, as in
--      popular.sql) in the seed's genre that the user hasn't played and that aren't picked
-- "Hasn't played" means within the window. The two rows of a user may share an episode.
--
-- Output, one row per recommendation, by user_id, seed_rank, item_rank
-- (at most 2 seeds x 10 items per user):
--   user_id
--   seed_rank        1 = most recent seed, 2 = the one before
--   seed_show_id
--   seed_episode_id
--   item_rank        1..10 within the seed's row
--   show_id
--   episode_id
--   score            co-listeners for a pick; 0 for filler
--   source           'co' or 'genre' (for debugging; the writer stores score only)
WITH play_events AS (
    SELECT user_id, show_id, episode_id, genre, event_id, server_ts
    FROM events
    WHERE dt BETWEEN ? AND ?
      AND server_ts >= ?
      AND server_ts < ?
      AND event_type = 'play'
),

-- 1. who played what
user_episodes AS (
    SELECT user_id, episode_id, MAX(server_ts) AS last_played
    FROM play_events
    GROUP BY user_id, episode_id
),

-- Per episode: its show and genre (fixed per episode) and distinct plays, for filler.
episodes AS (
    SELECT episode_id, MIN(show_id) AS show_id, MIN(genre) AS genre, COUNT(DISTINCT event_id) AS plays
    FROM play_events
    GROUP BY episode_id
),

-- 2. eligible users
eligible AS (
    SELECT user_id
    FROM user_episodes
    GROUP BY user_id
    HAVING COUNT(*) >= 3
),

-- 3. seeds
seeds AS (
    SELECT user_id, seed_rank, episode_id AS seed_episode_id
    FROM (
        SELECT
            ue.user_id,
            ue.episode_id,
            ROW_NUMBER() OVER (
                PARTITION BY ue.user_id ORDER BY ue.last_played DESC, ue.episode_id
            ) AS seed_rank
        FROM user_episodes ue
        JOIN eligible el ON el.user_id = ue.user_id
    ) ranked
    WHERE seed_rank <= 2
),

-- 4. co-listening, only for episodes that are someone's seed
co_counts AS (
    SELECT a.episode_id AS seed_episode_id, b.episode_id, COUNT(*) AS co_users
    FROM user_episodes a
    JOIN user_episodes b ON b.user_id = a.user_id AND b.episode_id <> a.episode_id
    WHERE a.episode_id IN (SELECT seed_episode_id FROM seeds)
    GROUP BY a.episode_id, b.episode_id
),

-- 5. picks
co_ranked AS (
    SELECT
        s.user_id,
        s.seed_rank,
        s.seed_episode_id,
        c.episode_id,
        c.co_users AS score,
        ROW_NUMBER() OVER (
            PARTITION BY s.user_id, s.seed_rank ORDER BY c.co_users DESC, c.episode_id
        ) AS item_rank
    FROM seeds s
    JOIN co_counts c ON c.seed_episode_id = s.seed_episode_id
    LEFT JOIN user_episodes played
        ON played.user_id = s.user_id AND played.episode_id = c.episode_id
    WHERE played.user_id IS NULL
),
co_picks AS (
    SELECT * FROM co_ranked WHERE item_rank <= 10
),
co_totals AS (
    SELECT user_id, seed_rank, COUNT(*) AS picked
    FROM co_picks
    GROUP BY user_id, seed_rank
),

-- 6. filler
genre_ranked AS (
    SELECT
        s.user_id,
        s.seed_rank,
        s.seed_episode_id,
        e.episode_id,
        ROW_NUMBER() OVER (
            PARTITION BY s.user_id, s.seed_rank ORDER BY e.plays DESC, e.episode_id
        ) AS filler_rank
    FROM seeds s
    JOIN episodes seed_episode ON seed_episode.episode_id = s.seed_episode_id
    JOIN episodes e ON e.genre = seed_episode.genre
    LEFT JOIN user_episodes played
        ON played.user_id = s.user_id AND played.episode_id = e.episode_id
    LEFT JOIN co_picks picked
        ON picked.user_id = s.user_id
        AND picked.seed_rank = s.seed_rank
        AND picked.episode_id = e.episode_id
    WHERE played.user_id IS NULL
      AND picked.user_id IS NULL
),

recommendations AS (
    SELECT
        user_id, seed_rank, seed_episode_id, item_rank, episode_id,
        CAST(score AS BIGINT) AS score,
        CAST('co' AS VARCHAR) AS source
    FROM co_picks
    UNION ALL
    SELECT
        g.user_id, g.seed_rank, g.seed_episode_id,
        COALESCE(t.picked, 0) + g.filler_rank AS item_rank,
        g.episode_id,
        CAST(0 AS BIGINT) AS score,
        CAST('genre' AS VARCHAR) AS source
    FROM genre_ranked g
    LEFT JOIN co_totals t ON t.user_id = g.user_id AND t.seed_rank = g.seed_rank
    WHERE COALESCE(t.picked, 0) + g.filler_rank <= 10
)

SELECT
    r.user_id,
    r.seed_rank,
    seed_episode.show_id AS seed_show_id,
    r.seed_episode_id,
    r.item_rank,
    e.show_id,
    r.episode_id,
    r.score,
    r.source
FROM recommendations r
JOIN episodes seed_episode ON seed_episode.episode_id = r.seed_episode_id
JOIN episodes e ON e.episode_id = r.episode_id
ORDER BY r.user_id, r.seed_rank, r.item_rank

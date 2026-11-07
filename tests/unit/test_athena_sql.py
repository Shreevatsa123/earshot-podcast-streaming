"""M5-03: the Athena queries in ``athena/``, run locally with DuckDB (CONTEXT §9, §10).

Each test writes a tiny lake to a temp folder exactly as Firehose lays it out
(``events/dt=YYYY-MM-DD/hour=HH/*.parquet``, partition columns only in the path), then
runs the real ``.sql`` file against it. DuckDB isn't Athena (Trino), so the queries stick
to SQL both support; the first run in real Athena is still the final proof.

Skipped when duckdb isn't installed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

duckdb = pytest.importorskip("duckdb", reason="duckdb isn't installed")
pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from earshot_infra.constructs.lake import EVENT_COLUMNS  # noqa: E402

ATHENA_DIR = Path(__file__).resolve().parents[2] / "athena"

#: The Glue table's columns (lake.py, M5-01) as DuckDB types, so the files match what
#: Firehose writes: Parquet INT32 for ``int``, INT64 for ``bigint``.
DUCKDB_TYPES = {"string": "VARCHAR", "int": "INTEGER", "bigint": "BIGINT"}
COLUMNS: tuple[tuple[str, str], ...] = tuple((name, DUCKDB_TYPES[kind]) for name, kind in EVENT_COLUMNS)


def ms(iso: str) -> int:
    """Epoch milliseconds of a UTC time such as ``2026-11-02T10:00:00``."""
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000)


_ids = iter(range(1, 1_000_000))


def event(**fields: Any) -> dict[str, Any]:
    """A valid §6 play event; override any field. ``arrival_ms`` sets the partition (default server_ts)."""
    n = next(_ids)
    base: dict[str, Any] = {
        "event_id": f"evt-{n:06d}",
        "schema_version": 1,
        "user_id": "sim-000001",
        "session_id": f"ses-{n:06d}",
        "show_id": "show-1",
        "episode_id": "ep-1",
        "genre": "true-crime",
        "event_type": "play",
        "position_sec": 0,
        "duration_sec": 2810,
        "client_ts": ms("2026-11-02T10:00:00"),
        "server_ts": ms("2026-11-02T10:00:00"),
        "region": "us-east",
        "device": "sim",
    }
    base.update(fields)
    return base


def write_lake(root: Path, events: list[dict[str, Any]]) -> Path:
    """Write ``events`` as Parquet under ``root/events/dt=.../hour=.../`` like Firehose does."""
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE ev ("
        + ", ".join(f"{name} {kind}" for name, kind in COLUMNS)
        + ", dt VARCHAR, hour VARCHAR)"
    )
    rows = []
    for e in events:
        arrival = datetime.fromtimestamp(e.get("arrival_ms", e["server_ts"]) / 1000, tz=timezone.utc)
        rows.append([e[name] for name, _ in COLUMNS] + [arrival.strftime("%Y-%m-%d"), arrival.strftime("%H")])
    con.executemany(f"INSERT INTO ev VALUES ({', '.join('?' * (len(COLUMNS) + 2))})", rows)
    root.mkdir(parents=True, exist_ok=True)
    lake = root / "events"
    con.execute(f"COPY ev TO '{lake.as_posix()}' (FORMAT parquet, PARTITION_BY (dt, hour))")
    con.close()
    return root


def lake_connection(root: Path) -> duckdb.DuckDBPyConnection:
    """A DuckDB connection with an ``events`` view shaped like the Glue table (dt/hour as strings)."""
    con = duckdb.connect()
    files = (root / "events").as_posix() + "/*/*/*.parquet"
    con.execute(
        f"CREATE VIEW events AS SELECT * FROM read_parquet('{files}', hive_partitioning = true, "
        "hive_types = {'dt': VARCHAR, 'hour': VARCHAR})"
    )
    return con


def run_query(root: Path, name: str, params: list[Any]) -> list[dict[str, Any]]:
    """Run ``athena/<name>.sql`` with positional parameters; rows as dicts."""
    sql = (ATHENA_DIR / f"{name}.sql").read_text(encoding="utf-8")
    con = lake_connection(root)
    cursor = con.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


# ---- Rules every query file follows -------------------------------------------------------

SQL_FILES = sorted(ATHENA_DIR.glob("*.sql"))


def _code(sql: str) -> str:
    """The SQL without ``--`` comment lines."""
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


@pytest.mark.parametrize("path", SQL_FILES, ids=lambda p: p.name)
def test_query_documents_each_parameter(path: Path):
    """The caller (Step Functions, scripts) passes parameters by position, so the header is the API."""
    sql = path.read_text(encoding="utf-8")
    block = re.search(r"^-- Parameters, in order.*?\n((?:--.*\S.*\n)+)", sql, flags=re.MULTILINE)
    assert block, f"{path.name}: no 'Parameters, in order' list in the header"
    documented = re.findall(r"^--\s+\d+\.\s+\w+", block.group(1), flags=re.MULTILINE)
    assert _code(sql).count("?") == len(documented)


@pytest.mark.parametrize("path", SQL_FILES, ids=lambda p: p.name)
def test_query_takes_time_from_parameters_not_the_clock(path: Path):
    """No current_date/now(): results must be reproducible, and dt must stay a literal for pruning."""
    code = _code(path.read_text(encoding="utf-8")).lower()
    assert not re.search(r"current_date|current_timestamp|\bnow\s*\(|localtimestamp", code)


@pytest.mark.parametrize("path", SQL_FILES, ids=lambda p: p.name)
def test_query_filters_on_dt(path: Path):
    """Without a dt filter Athena scans the whole lake (cost, and the 1 GB cutoff)."""
    assert re.search(r"\bdt\s+between\b", _code(path.read_text(encoding="utf-8")).lower())


# ---- count_events.sql ---------------------------------------------------------------------

WINDOW_START = ms("2026-11-02T10:00:00")
WINDOW_END = ms("2026-11-02T10:10:00")


def count_events(root: Path, dt_from: str, dt_to: str, start: int, end: int) -> dict[str, Any]:
    (row,) = run_query(root, "count_events", [dt_from, dt_to, start, end])
    return row


def test_count_events_counts_duplicates_once(tmp_path):
    first = event()
    duplicate = dict(first)
    write_lake(tmp_path, [first, duplicate, event()])
    result = count_events(tmp_path, "2026-11-02", "2026-11-03", WINDOW_START, WINDOW_END)
    assert result == {"total_rows": 3, "distinct_events": 2}


def test_count_events_window_is_start_inclusive_end_exclusive(tmp_path):
    write_lake(
        tmp_path,
        [
            event(server_ts=WINDOW_START - 1),
            event(server_ts=WINDOW_START),
            event(server_ts=WINDOW_END - 1),
            event(server_ts=WINDOW_END),
        ],
    )
    result = count_events(tmp_path, "2026-11-02", "2026-11-03", WINDOW_START, WINDOW_END)
    assert result["distinct_events"] == 2


def test_count_events_finds_late_arrivals_in_the_next_dt(tmp_path):
    """server_ts is 23:59:59.900 but Firehose stamped it after midnight, so it sits in the next dt."""
    late = event(server_ts=ms("2026-11-02T23:59:59.900"), arrival_ms=ms("2026-11-03T00:00:00.400"))
    write_lake(tmp_path, [late])
    day_start, day_end = ms("2026-11-02T00:00:00"), ms("2026-11-03T00:00:00")
    assert count_events(tmp_path, "2026-11-02", "2026-11-03", day_start, day_end)["distinct_events"] == 1
    # Scanning only the event's own date misses it: why dt_to is the day after the window.
    assert count_events(tmp_path, "2026-11-02", "2026-11-02", day_start, day_end)["distinct_events"] == 0


def test_count_events_ignores_partitions_outside_dt_range(tmp_path):
    write_lake(tmp_path, [event(), event(server_ts=ms("2026-11-05T10:00:00"))])
    result = count_events(tmp_path, "2026-11-02", "2026-11-03", WINDOW_START, ms("2026-11-06T00:00:00"))
    assert result["distinct_events"] == 1


# ---- popular.sql --------------------------------------------------------------------------

# The recs job's 7-day window ending 2026-11-03 00:00 UTC; default events (11-02 10:00) fall inside.
WEEK = ["2026-10-27", "2026-11-03", ms("2026-10-27T00:00:00"), ms("2026-11-03T00:00:00")]


def plays(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return [(row["episode_id"], row["plays"]) for row in rows]


def test_popular_counts_distinct_play_events_only(tmp_path):
    first = event(episode_id="ep-1")
    write_lake(
        tmp_path,
        [
            first,
            dict(first),  # duplicate: counts once
            event(episode_id="ep-1"),
            event(episode_id="ep-1", event_type="pause"),
            event(episode_id="ep-1", event_type="heartbeat"),
            event(episode_id="ep-2", event_type="complete"),  # no plays at all: no row
        ],
    )
    assert run_query(tmp_path, "popular", WEEK) == [{"show_id": "show-1", "episode_id": "ep-1", "plays": 2}]


def test_popular_ranks_by_plays_then_episode_id(tmp_path):
    counts = {"ep-a": 2, "ep-b": 3, "ep-c": 2}
    write_lake(tmp_path, [event(episode_id=ep) for ep, n in counts.items() for _ in range(n)])
    assert plays(run_query(tmp_path, "popular", WEEK)) == [("ep-b", 3), ("ep-a", 2), ("ep-c", 2)]


def test_popular_returns_at_most_20(tmp_path):
    write_lake(tmp_path, [event(episode_id=f"ep-{n:02d}") for n in range(1, 22)])
    rows = run_query(tmp_path, "popular", WEEK)
    assert [row["episode_id"] for row in rows] == [f"ep-{n:02d}" for n in range(1, 21)]


def test_popular_uses_the_window_including_late_arrivals(tmp_path):
    start, end = WEEK[2], WEEK[3]
    write_lake(
        tmp_path,
        [
            event(episode_id="too-early", server_ts=start - 1),
            event(episode_id="first-ms", server_ts=start),
            event(episode_id="late", server_ts=end - 100, arrival_ms=end + 300),  # in dt=2026-11-03
            event(episode_id="too-late", server_ts=end),
        ],
    )
    assert sorted(row["episode_id"] for row in run_query(tmp_path, "popular", WEEK)) == ["first-ms", "late"]


# ---- reconcile_trending.sql ---------------------------------------------------------------

# One UTC day, D = 2026-11-02: dt from D to D+1, server_ts in [D 00:00, D+1 00:00).
DAY = ["2026-11-02", "2026-11-03", ms("2026-11-02T00:00:00"), ms("2026-11-03T00:00:00")]


def test_reconcile_counts_distinct_plays_per_episode(tmp_path):
    first = event(episode_id="ep-1")
    write_lake(
        tmp_path,
        [
            first,
            dict(first),
            event(episode_id="ep-1"),
            event(episode_id="ep-2", show_id="show-2"),
            event(episode_id="ep-2", show_id="show-2", event_type="pause"),
        ],
    )
    assert run_query(tmp_path, "reconcile_trending", DAY) == [
        {"show_id": "show-1", "episode_id": "ep-1", "plays": 2},
        {"show_id": "show-2", "episode_id": "ep-2", "plays": 1},
    ]


def test_reconcile_follows_server_ts_across_midnight(tmp_path):
    """Trending's day is the UTC date of server_ts (§6), not the dt folder the file landed in."""
    write_lake(
        tmp_path,
        [
            # The previous day's play that landed in D's folder: not D's.
            event(
                episode_id="yesterday",
                server_ts=ms("2026-11-01T23:59:59.900"),
                arrival_ms=ms("2026-11-02T00:00:00.300"),
            ),
            # D's play that landed in D+1's folder: D's.
            event(
                episode_id="late-today",
                server_ts=ms("2026-11-02T23:59:59.800"),
                arrival_ms=ms("2026-11-03T00:00:00.200"),
            ),
            event(episode_id="tomorrow", server_ts=ms("2026-11-03T00:00:00")),
        ],
    )
    assert plays(run_query(tmp_path, "reconcile_trending", DAY)) == [("late-today", 1)]


# ---- recs.sql -----------------------------------------------------------------------------

# The recs job's 30-day window ending 2026-11-03 00:00 UTC.
MONTH = ["2026-10-04", "2026-11-03", ms("2026-10-04T00:00:00"), ms("2026-11-03T00:00:00")]
MINUTE = 60_000
T0 = ms("2026-11-02T10:00:00")


def play(user: str, episode: str, minute: int = 0, genre: str = "true-crime", **fields: Any) -> dict[str, Any]:
    """A play of ``episode`` by ``user`` at T0 + ``minute``; each episode is its own show."""
    defaults = {"show_id": f"show-{episode}", "genre": genre, "server_ts": T0 + minute * MINUTE}
    return event(user_id=user, episode_id=episode, **{**defaults, **fields})


def crowd(episode: str, listeners: int, genre: str) -> list[dict[str, Any]]:
    """``listeners`` different one-off users playing ``episode``: popularity without co-listening."""
    return [play(f"crowd-{episode}-{n}", episode, genre=genre) for n in range(listeners)]


def recs(root: Path) -> list[dict[str, Any]]:
    return run_query(root, "recs", MONTH)


def row(rows: list[dict[str, Any]], user: str, seed_rank: int) -> list[tuple[str, int, str]]:
    """One "Because you listened to" row as (episode_id, score, source), checking item_rank is 1..n."""
    items = [r for r in rows if r["user_id"] == user and r["seed_rank"] == seed_rank]
    assert [r["item_rank"] for r in items] == list(range(1, len(items) + 1))
    return [(r["episode_id"], r["score"], r["source"]) for r in items]


def seeds(rows: list[dict[str, Any]], user: str) -> list[str]:
    return [r["seed_episode_id"] for r in rows if r["user_id"] == user and r["item_rank"] == 1]


def test_recs_only_for_users_with_3_distinct_plays(tmp_path):
    write_lake(
        tmp_path,
        [
            play("two", "a1", 1),
            play("two", "a2", 2),
            play("two", "a2", 3),  # a replay isn't a third episode
            play("three", "a1", 1),
            play("three", "a2", 2),
            play("three", "a3", 3),
            play("other", "a4", 4),  # gives "three" something unplayed in the genre
        ],
    )
    assert {r["user_id"] for r in recs(tmp_path)} == {"three"}


def test_recs_ignore_non_plays_and_plays_outside_the_window(tmp_path):
    write_lake(
        tmp_path,
        [
            play("u1", "w1", 1),
            play("u1", "w2", 2),
            play("u1", "w3", 3, event_type="pause"),
            play("u1", "w4", server_ts=MONTH[2] - 1),  # just before the window
            play("other", "w5", 5),
        ],
    )
    assert recs(tmp_path) == []


def test_recs_seeds_are_the_two_most_recent_episodes(tmp_path):
    write_lake(
        tmp_path,
        [
            play("u1", "b1", 1),
            play("u1", "b2", 2),
            play("u1", "b3", 3),
            play("u1", "b1", 10),  # replaying b1 makes it the most recent
            play("u2", "c3", 5),  # three episodes at the same minute: ties go to the lower id
            play("u2", "c1", 5),
            play("u2", "c2", 5),
            play("other", "z1", 0),
        ],
    )
    rows = recs(tmp_path)
    assert seeds(rows, "u1") == ["b1", "b3"]
    assert seeds(rows, "u2") == ["c1", "c2"]


def test_recs_rank_co_listened_episodes_the_user_has_not_played(tmp_path):
    co_genre = "comedy"  # different from the seeds' genre, so no filler joins the row
    duplicate = play("u4", "x3", genre=co_genre)
    write_lake(
        tmp_path,
        [
            play("u1", "e1", 1),
            play("u1", "e2", 2),
            play("u1", "e3", 3),
            play("u2", "e3"),
            play("u2", "x1", genre=co_genre),
            play("u2", "x2", genre=co_genre),
            play("u3", "e3"),
            play("u3", "x1", genre=co_genre),
            play("u4", "e3"),
            play("u4", "x2", genre=co_genre),
            duplicate,
            dict(duplicate),  # a duplicate event and replays count u4 once for x3
            play("u4", "x3", 30, genre=co_genre),
            play("u5", "x3", genre=co_genre),  # never played e3: not a co-listener
        ],
    )
    rows = recs(tmp_path)
    # Seed e3: x1 and x2 have 2 co-listeners each (tie -> lower id first), x3 has 1.
    # e1 and e2 were co-played too, but u1 already played them.
    assert row(rows, "u1", 1) == [("x1", 2, "co"), ("x2", 2, "co"), ("x3", 1, "co")]
    # Seed e2: only u1 played it and every true-crime episode is played: no row at all.
    assert row(rows, "u1", 2) == []


def test_recs_keep_at_most_10_picks_per_seed(tmp_path):
    events = [play("u1", "k1", 1), play("u1", "k2", 2), play("u1", "k0", 3)]
    for n in range(1, 13):  # 12 one-co-listener candidates for seed k0
        events += [play(f"fan-{n}", "k0"), play(f"fan-{n}", f"y{n:02d}", genre="comedy")]
    write_lake(tmp_path, events)
    assert row(recs(tmp_path), "u1", 1) == [(f"y{n:02d}", 1, "co") for n in range(1, 11)]


def test_recs_fill_from_the_seed_genre_by_popularity(tmp_path):
    events = [play("u1", "s1", 1, genre="news"), play("u1", "s2", 2, genre="news")]
    events += [play("u1", "s3", 3, genre="news"), play("u1", "n01", 4, genre="news")]
    for n in range(1, 13):  # n01 is the most played, n12 the least
        events += crowd(f"n{n:02d}", 13 - n, genre="news")
    events += crowd("loud", 50, genre="comedy")  # popular, but the wrong genre
    write_lake(tmp_path, events)
    rows = recs(tmp_path)
    # Most recent seed is n01 (played last). Nobody else played the seeds: all filler.
    # n01 and s1-s3 are played, so filler is n02..n11; n12 doesn't fit in 10.
    assert seeds(rows, "u1") == ["n01", "s3"]
    assert row(rows, "u1", 1) == [(f"n{n:02d}", 0, "genre") for n in range(2, 12)]


def test_recs_filler_continues_after_picks_without_repeating_them(tmp_path):
    events = [play("u1", "m1", 1, genre="science"), play("u1", "m2", 2, genre="science")]
    events += [play("u1", "m3", 3, genre="science")]
    events += [play("u2", "m3", genre="science"), play("u2", "p1", genre="science")]
    events += crowd("p1", 5, "science") + crowd("p2", 3, "science") + crowd("p3", 1, "science")
    write_lake(tmp_path, events)
    # p1 is a pick (u2 played m3 and p1); filler follows by popularity and skips p1.
    assert row(recs(tmp_path), "u1", 1) == [("p1", 1, "co"), ("p2", 0, "genre"), ("p3", 0, "genre")]


def test_recs_output_columns_and_show_ids(tmp_path):
    write_lake(
        tmp_path,
        [play("u1", "e1", 1), play("u1", "e2", 2), play("u1", "e3", 3), play("u2", "e3"), play("u2", "x1")],
    )
    first = recs(tmp_path)[0]
    assert first == {
        "user_id": "u1",
        "seed_rank": 1,
        "seed_show_id": "show-e3",
        "seed_episode_id": "e3",
        "item_rank": 1,
        "show_id": "show-x1",
        "episode_id": "x1",
        "score": 1,
        "source": "co",
    }

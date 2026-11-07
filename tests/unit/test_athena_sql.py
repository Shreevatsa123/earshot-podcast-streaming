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
    documented = re.findall(r"^--\s+\d+\.\s+\w+", sql, flags=re.MULTILINE)
    assert documented, f"{path.name}: no 'Parameters, in order' list in the header"
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

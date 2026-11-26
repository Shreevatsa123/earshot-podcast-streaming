"""M5-04: the recs writer (CONTEXT §8.1, §10): Athena's CSVs -> RECS and POPULAR items."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from typing import Any

import pytest

from recs_writer import handler
from recs_writer.handler import (
    POPULAR_COLUMNS,
    RECS_COLUMNS,
    ResultError,
    parse_popular,
    parse_recs,
    popular_item,
    recs_item,
)


def athena_csv(columns: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    """A result file the way Athena writes it: a header, then every value in double quotes."""
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return out.getvalue()


def rec(user: str, seed_rank: int, seed_ep: str, item_rank: int, ep: str, score: int = 1, source: str = "co"):
    """One recs.sql output row; each episode is its own show (show-<episode>)."""
    return (user, seed_rank, f"show-{seed_ep}", seed_ep, item_rank, f"show-{ep}", ep, score, source)


def recs_csv(*rows: tuple[Any, ...]) -> str:
    return athena_csv(RECS_COLUMNS, list(rows))


# ---- parse_recs ---------------------------------------------------------------------------


def test_recs_become_one_item_per_user_in_rank_order():
    text = recs_csv(
        rec("u1", 2, "s2", 1, "x9", 4),
        rec("u1", 1, "s1", 2, "x2", 3),  # file order doesn't matter
        rec("u1", 1, "s1", 1, "x1", 5),
        rec("u2", 1, "t1", 1, "y1", 0, "genre"),
    )
    assert parse_recs(text) == {
        "u1": [
            {
                "seed_show_id": "show-s1",
                "seed_episode_id": "s1",
                "items": [
                    {"show_id": "show-x1", "episode_id": "x1", "score": 5},
                    {"show_id": "show-x2", "episode_id": "x2", "score": 3},
                ],
            },
            {
                "seed_show_id": "show-s2",
                "seed_episode_id": "s2",
                "items": [{"show_id": "show-x9", "episode_id": "x9", "score": 4}],
            },
        ],
        "u2": [{"seed_show_id": "show-t1", "seed_episode_id": "t1", "items": [{"show_id": "show-y1", "episode_id": "y1", "score": 0}]}],
    }


def test_item_ranks_sort_as_numbers_not_text():
    """Athena quotes numbers, so "10" sorts before "2" unless they're converted."""
    text = recs_csv(*(rec("u1", 1, "s1", rank, f"x{rank:02d}") for rank in (10, 2, 1, 9, 3, 4, 5, 6, 7, 8)))
    items = parse_recs(text)["u1"][0]["items"]
    assert [item["episode_id"] for item in items] == [f"x{n:02d}" for n in range(1, 11)]
    assert all(isinstance(item["score"], int) for item in items)


def test_a_user_can_have_only_a_second_seed_row():
    """Seed 1 can run out of recommendations while seed 2 still has some."""
    assert [r["seed_episode_id"] for r in parse_recs(recs_csv(rec("u1", 2, "s2", 1, "x1")))["u1"]] == ["s2"]


def test_header_only_means_no_users():
    assert parse_recs(recs_csv()) == {}


@pytest.mark.parametrize(
    "text",
    [
        recs_csv(rec("u1", 3, "s3", 1, "x1")),  # a third row
        recs_csv(rec("u1", 1, "s1", 11, "x1")),  # an 11th item
        recs_csv(rec("u1", 1, "s1", 0, "x1")),
        recs_csv(rec("u1", 1, "s1", 1, "x1", -1)),  # negative score
        recs_csv(rec("u1", 1, "s1", 1, "x1"), rec("u1", 1, "other", 2, "x2")),  # seed changes
        recs_csv(rec("u1", 1, "s1", 1, "x1"), rec("u1", 1, "s1", 1, "x2")),  # rank repeated
        recs_csv(rec("u1", 1, "s1", 1, "x1"), rec("u1", 1, "s1", 3, "x3")),  # rank 2 missing
        recs_csv(("u1", "one", "show-s1", "s1", 1, "show-x1", "x1", 1, "co")),  # not a number
        recs_csv(("", 1, "show-s1", "s1", 1, "show-x1", "x1", 1, "co")),  # empty user
        athena_csv(("user_id", "seed_rank"), [("u1", 1)]),  # wrong columns
        "",  # no header at all
    ],
    ids=[
        "seed-rank-3",
        "item-rank-11",
        "item-rank-0",
        "negative-score",
        "seed-changes",
        "rank-repeated",
        "rank-gap",
        "not-a-number",
        "empty-user",
        "wrong-columns",
        "no-header",
    ],
)
def test_malformed_recs_fail_the_whole_run(text):
    with pytest.raises(ResultError):
        parse_recs(text)


# ---- parse_popular ------------------------------------------------------------------------


def popular_csv(*rows: tuple[Any, ...]) -> str:
    return athena_csv(POPULAR_COLUMNS, list(rows))


def test_popular_keeps_the_query_order_with_integer_plays():
    text = popular_csv(("show-b", "b", 12), ("show-a", "a", 7), ("show-c", "c", 7))
    assert parse_popular(text) == [
        {"show_id": "show-b", "episode_id": "b", "plays": 12},
        {"show_id": "show-a", "episode_id": "a", "plays": 7},
        {"show_id": "show-c", "episode_id": "c", "plays": 7},
    ]


def test_empty_popular():
    assert parse_popular(popular_csv()) == []


@pytest.mark.parametrize(
    "text",
    [
        popular_csv(*((f"show-{n}", f"e{n}", 1) for n in range(21))),  # 21 episodes
        popular_csv(("show-a", "a", 2), ("show-a", "a", 1)),  # repeated episode
        popular_csv(("show-a", "a", 0)),
        popular_csv(("show-a", "a", "many")),
        athena_csv(("episode_id", "plays"), [("a", 1)]),
    ],
    ids=["21-episodes", "repeated", "zero-plays", "not-a-number", "wrong-columns"],
)
def test_malformed_popular_fails_the_whole_run(text):
    with pytest.raises(ResultError):
        parse_popular(text)


# ---- Items --------------------------------------------------------------------------------


def test_recs_item_shape_matches_what_home_reads():
    """§8.1, and the fields M2's /home uses: rows[:2], seed_show_id, seed_episode_id, items[].show_id/episode_id."""
    rows = parse_recs(recs_csv(rec("sim-000042", 1, "s1", 1, "x1", 2)))["sim-000042"]
    item = recs_item("sim-000042", rows, run_id="run-1", generated_at=1_794_614_400_000)
    assert item == {
        "PK": "USER#sim-000042",
        "SK": "RECS",
        "rows": rows,
        "generated_at": 1_794_614_400_000,
        "run_id": "run-1",
    }
    assert set(item["rows"][0]) == {"seed_show_id", "seed_episode_id", "items"}
    assert set(item["rows"][0]["items"][0]) == {"show_id", "episode_id", "score"}


def test_popular_item_shape():
    items = parse_popular(popular_csv(("show-a", "a", 3)))
    assert popular_item(items, run_id="run-1", generated_at=5) == {
        "PK": "POPULAR",
        "SK": "GLOBAL",
        "items": [{"show_id": "show-a", "episode_id": "a", "plays": 3}],
        "generated_at": 5,
        "run_id": "run-1",
    }


# ---- main: S3 in, DynamoDB out (moto) -----------------------------------------------------

LAKE = "earshot-test-lake"
NOW = 1_794_614_400_000


def plain(value: Any) -> Any:
    """DynamoDB returns numbers as Decimal; compare them as ints."""
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


@pytest.fixture
def aws(ddb_table, monkeypatch):
    """The shared moto table (conftest) plus a lake bucket, the function's env, and a fixed clock."""
    import boto3

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=LAKE)
    monkeypatch.setenv("TABLE_NAME", ddb_table.name)
    monkeypatch.setenv("LAKE_BUCKET", LAKE)
    monkeypatch.setattr(handler.clock, "now_ms", lambda: NOW)
    return s3, ddb_table


def run(s3: Any, recs_text: str, popular_text: str, run_id: str = "run-1") -> dict[str, Any]:
    """Put both results where Athena would and invoke the writer like the state machine will."""
    recs_key, popular_key = f"recs-runs/{run_id}/recs.csv", f"recs-runs/{run_id}/popular.csv"
    s3.put_object(Bucket=LAKE, Key=recs_key, Body=recs_text.encode("utf-8"))
    s3.put_object(Bucket=LAKE, Key=popular_key, Body=popular_text.encode("utf-8"))
    event = {"run_id": run_id, "recs_csv": f"s3://{LAKE}/{recs_key}", "popular_csv": f"s3://{LAKE}/{popular_key}"}
    return handler.main(event, None)


def get(table: Any, pk: str, sk: str) -> dict[str, Any] | None:
    item = table.get_item(Key={"PK": pk, "SK": sk}).get("Item")
    return plain(item) if item else None


def test_main_writes_recs_and_popular(aws, capsys):
    s3, table = aws
    result = run(
        s3,
        recs_csv(rec("u1", 1, "s1", 1, "x1", 3), rec("u1", 2, "s2", 1, "x2", 1), rec("u2", 1, "t1", 1, "y1", 0)),
        popular_csv(("show-a", "a", 9), ("show-b", "b", 4)),
    )
    assert result == {"run_id": "run-1", "users_written": 2, "popular_count": 2}
    u1 = get(table, "USER#u1", "RECS")
    assert [r["seed_episode_id"] for r in u1["rows"]] == ["s1", "s2"]
    assert (u1["generated_at"], u1["run_id"]) == (NOW, "run-1")
    assert get(table, "USER#u2", "RECS")["rows"][0]["items"] == [{"show_id": "show-y1", "episode_id": "y1", "score": 0}]
    assert get(table, "POPULAR", "GLOBAL") == {
        "PK": "POPULAR",
        "SK": "GLOBAL",
        "items": [{"show_id": "show-a", "episode_id": "a", "plays": 9}, {"show_id": "show-b", "episode_id": "b", "plays": 4}],
        "generated_at": NOW,
        "run_id": "run-1",
    }
    logged = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    metric = next(doc for doc in logged if "_aws" in doc)
    assert metric["RecsUsersWritten"] == 2
    assert metric["_aws"]["CloudWatchMetrics"][0]["Metrics"] == [{"Name": "RecsUsersWritten", "Unit": "Count"}]


def test_main_replaces_a_users_item_whole_and_keeps_users_who_dropped_out(aws):
    s3, table = aws
    table.put_item(Item={"PK": "USER#u1", "SK": "RECS", "rows": [], "run_id": "old", "leftover": "x"})
    table.put_item(Item={"PK": "USER#gone", "SK": "RECS", "rows": [], "run_id": "old"})
    run(s3, recs_csv(rec("u1", 1, "s1", 1, "x1")), popular_csv())
    u1 = get(table, "USER#u1", "RECS")
    assert u1["run_id"] == "run-1" and "leftover" not in u1
    assert get(table, "USER#gone", "RECS")["run_id"] == "old"  # decision: no cleanup scan


def test_main_writes_many_users_through_batches(aws):
    """More than 25 users, so the batch writer has to split the writes."""
    s3, table = aws
    rows = [rec(f"sim-{n:06d}", 1, "s1", 1, "x1") for n in range(60)]
    assert run(s3, recs_csv(*rows), popular_csv())["users_written"] == 60
    assert table.scan(Select="COUNT")["Count"] == 61  # 60 RECS + POPULAR


def test_main_writes_an_empty_popular_item(aws):
    s3, table = aws
    assert run(s3, recs_csv(), popular_csv()) == {"run_id": "run-1", "users_written": 0, "popular_count": 0}
    assert get(table, "POPULAR", "GLOBAL")["items"] == []


def test_main_writes_nothing_when_a_result_is_malformed(aws):
    s3, table = aws
    table.put_item(Item={"PK": "POPULAR", "SK": "GLOBAL", "items": [], "run_id": "yesterday"})
    good_recs = recs_csv(rec("u1", 1, "s1", 1, "x1"))
    bad_popular = popular_csv(("show-a", "a", "lots"))
    with pytest.raises(ResultError):
        run(s3, good_recs, bad_popular)
    assert get(table, "USER#u1", "RECS") is None  # recs parsed fine, but nothing was written
    assert get(table, "POPULAR", "GLOBAL")["run_id"] == "yesterday"


@pytest.mark.parametrize(
    "event",
    [
        {"run_id": "", "recs_csv": f"s3://{LAKE}/recs-runs/r/a.csv", "popular_csv": f"s3://{LAKE}/recs-runs/r/b.csv"},
        {"run_id": "r", "recs_csv": f"s3://{LAKE}/events/dt=2026-11-14/x.json.gz", "popular_csv": f"s3://{LAKE}/recs-runs/r/b.csv"},
        {"run_id": "r", "recs_csv": "s3://someone-elses-bucket/recs-runs/r/a.csv", "popular_csv": f"s3://{LAKE}/recs-runs/r/b.csv"},
        {"run_id": "r", "recs_csv": f"s3://{LAKE}/recs-runs/", "popular_csv": f"s3://{LAKE}/recs-runs/r/b.csv"},
        {"run_id": "r", "popular_csv": f"s3://{LAKE}/recs-runs/r/b.csv"},
    ],
    ids=["no-run-id", "outside-recs-runs", "other-bucket", "prefix-only", "missing-path"],
)
def test_main_refuses_bad_input_before_touching_aws(event, monkeypatch):
    def no_aws(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no AWS call expected")

    monkeypatch.setattr(handler.boto3, "client", no_aws)
    monkeypatch.setattr(handler.boto3, "resource", no_aws)
    monkeypatch.setenv("LAKE_BUCKET", LAKE)
    with pytest.raises(ValueError):
        handler.main(event, None)


# ---- End to end: archiver files -> athena/*.sql -> Athena-style CSV -> writer -> items -------


def test_the_real_queries_output_becomes_valid_items(aws, tmp_path):
    """M3's 1,000 sample events go through the archiver's file format, recs.sql and popular.sql
    (in DuckDB), then the writer. Every item must have the §8.1 shape and the right counts."""
    duckdb = pytest.importorskip("duckdb", reason="duckdb isn't installed")
    pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")
    from pathlib import Path

    from archiver.handler import encode_lines, object_key, plan_batch
    from earshot_infra.constructs.lake import EVENT_COLUMNS

    root = Path(__file__).resolve().parents[2]
    lines = (root / "contracts" / "samples" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    batch = [{"messageId": f"m{i}", "body": json.dumps({"events": events[i : i + 25]})} for i in range(0, 1000, 25)]
    for n, (folder, folder_lines) in enumerate(plan_batch(batch).lines_by_folder.items()):
        path = tmp_path / object_key(folder, f"f{n}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encode_lines(folder_lines))

    types = {"string": "VARCHAR", "int": "INTEGER", "bigint": "BIGINT"}
    columns = ", ".join(f"'{name}': '{types[kind]}'" for name, kind in EVENT_COLUMNS)
    con = duckdb.connect()
    con.execute(
        f"CREATE VIEW events AS SELECT * FROM read_json('{(tmp_path / 'events').as_posix()}/*/*/*.json.gz', "
        f"format = 'newline_delimited', columns = {{{columns}}}, hive_partitioning = true, "
        "hive_types = {'dt': VARCHAR, 'hour': VARCHAR})"
    )
    window = ["2026-11-14", "2026-11-15", 1_794_614_400_000, 1_794_700_800_000]  # the sample's day

    def query_as_athena_csv(name: str) -> tuple[str, list[tuple[Any, ...]]]:
        cursor = con.execute((root / "athena" / f"{name}.sql").read_text(encoding="utf-8"), window)
        rows = cursor.fetchall()
        return athena_csv(tuple(d[0] for d in cursor.description), rows), rows

    recs_text, recs_rows = query_as_athena_csv("recs")
    popular_text, popular_rows = query_as_athena_csv("popular")
    s3, table = aws
    result = run(s3, recs_text, popular_text)

    users = sorted({row[0] for row in recs_rows})
    assert users, "the sample should have at least one user with 3+ distinct plays"
    assert result == {"run_id": "run-1", "users_written": len(users), "popular_count": len(popular_rows)}
    for user in users:
        item = get(table, f"USER#{user}", "RECS")
        assert 1 <= len(item["rows"]) <= 2
        for row in item["rows"]:
            assert set(row) == {"seed_show_id", "seed_episode_id", "items"}
            assert 1 <= len(row["items"]) <= 10
            assert all(set(i) == {"show_id", "episode_id", "score"} for i in row["items"])
        assert sum(len(r["items"]) for r in item["rows"]) == sum(1 for r in recs_rows if r[0] == user)
    popular = get(table, "POPULAR", "GLOBAL")["items"]
    assert [(p["episode_id"], p["plays"]) for p in popular] == [(r[1], r[2]) for r in popular_rows]

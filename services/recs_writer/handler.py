"""Recs writer Lambda: Athena result CSVs -> RECS + POPULAR items (CONTEXT §8.1, §10).

Owner: M5 · Tracker: M5-04 · Function: ``earshot-<stage>-recs-writer`` · Handler: ``recs_writer.handler.main``
Env (CONTEXT §9): STAGE, TABLE_NAME, LAKE_BUCKET.

Input (from the recs state machine, M5-05): ``{"run_id", "recs_csv", "popular_csv"}``, the
``s3://`` paths of the two Athena results under ``recs-runs/<run_id>/``.

- ``recs.sql`` returns one row per recommendation; each user becomes one RECS item with
  up to 2 rows (by ``seed_rank``) of up to 10 items (by ``item_rank``).
- ``popular.sql`` returns up to 20 episodes, most played first; they become the POPULAR item.
- Both files are parsed completely before anything is written: a malformed row means a
  query bug, so the run fails and yesterday's items stay instead of being half-replaced.
- A user who no longer qualifies keeps their last RECS item (no cleanup scan; §15).
- Paths outside ``s3://<lake>/recs-runs/`` are refused, so the writer can't be pointed at
  arbitrary files.

Emits ``RecsUsersWritten`` (§10) and one JSON log line per run.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import boto3

from shared import clock, log
from shared.names import RECS_RUNS_PREFIX, required_env

#: recs.sql's output columns, in order (see its header).
RECS_COLUMNS = (
    "user_id",
    "seed_rank",
    "seed_show_id",
    "seed_episode_id",
    "item_rank",
    "show_id",
    "episode_id",
    "score",
    "source",
)
#: popular.sql's output columns, in order.
POPULAR_COLUMNS = ("show_id", "episode_id", "plays")

MAX_ROWS = 2  # "Because you listened to" rows per user (§8.1)
MAX_ITEMS = 10  # items per row
MAX_POPULAR = 20  # POPULAR items


class ResultError(ValueError):
    """An Athena result that doesn't look like the query's documented output."""


def read_csv(text: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
    """Rows of an Athena result CSV as dicts. Athena quotes every value, numbers included."""
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != columns:
        raise ResultError(f"expected columns {list(columns)}, got {reader.fieldnames}")
    return list(reader)


def _int(row: dict[str, str], name: str, line: int) -> int:
    try:
        return int(row[name])
    except (TypeError, ValueError):
        raise ResultError(f"line {line}: {name} must be an integer, got {row[name]!r}") from None


def _text(row: dict[str, str], name: str, line: int) -> str:
    value = row[name]
    if not value:
        raise ResultError(f"line {line}: {name} is empty")
    return value


def parse_recs(text: str) -> dict[str, list[dict[str, Any]]]:
    """recs.sql's CSV -> ``{user_id: rows}`` in the RECS item's §8.1 shape.

    Each row is ``{seed_show_id, seed_episode_id, items: [{show_id, episode_id, score}]}``,
    rows ordered by ``seed_rank`` and items by ``item_rank``. A user can have only a
    seed 2 row when seed 1 had nothing left to recommend.
    """
    seeds: dict[str, dict[int, dict[str, Any]]] = {}
    for line, row in enumerate(read_csv(text, RECS_COLUMNS), start=2):  # line 1 is the header
        user_id = _text(row, "user_id", line)
        seed_rank = _int(row, "seed_rank", line)
        item_rank = _int(row, "item_rank", line)
        score = _int(row, "score", line)
        if not 1 <= seed_rank <= MAX_ROWS:
            raise ResultError(f"line {line}: seed_rank {seed_rank} is outside 1..{MAX_ROWS}")
        if not 1 <= item_rank <= MAX_ITEMS:
            raise ResultError(f"line {line}: item_rank {item_rank} is outside 1..{MAX_ITEMS}")
        if score < 0:
            raise ResultError(f"line {line}: score {score} is negative")
        seed = (_text(row, "seed_show_id", line), _text(row, "seed_episode_id", line))
        entry = seeds.setdefault(user_id, {}).setdefault(seed_rank, {"seed": seed, "items": {}})
        if entry["seed"] != seed:
            raise ResultError(f"line {line}: {user_id} seed {seed_rank} changes from {entry['seed']} to {seed}")
        if item_rank in entry["items"]:
            raise ResultError(f"line {line}: {user_id} seed {seed_rank} repeats item_rank {item_rank}")
        entry["items"][item_rank] = {
            "show_id": _text(row, "show_id", line),
            "episode_id": _text(row, "episode_id", line),
            "score": score,
        }

    recs: dict[str, list[dict[str, Any]]] = {}
    for user_id, by_rank in seeds.items():
        rows = []
        for seed_rank in sorted(by_rank):
            entry = by_rank[seed_rank]
            ranks = sorted(entry["items"])
            if ranks != list(range(1, len(ranks) + 1)):
                raise ResultError(f"{user_id} seed {seed_rank}: item_rank must run 1..n, got {ranks}")
            seed_show_id, seed_episode_id = entry["seed"]
            rows.append(
                {
                    "seed_show_id": seed_show_id,
                    "seed_episode_id": seed_episode_id,
                    "items": [entry["items"][rank] for rank in ranks],
                }
            )
        recs[user_id] = rows
    return recs


def parse_popular(text: str) -> list[dict[str, Any]]:
    """popular.sql's CSV -> the POPULAR item's ``items``, in the query's order (most played first)."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line, row in enumerate(read_csv(text, POPULAR_COLUMNS), start=2):
        episode_id = _text(row, "episode_id", line)
        plays = _int(row, "plays", line)
        if plays < 1:
            raise ResultError(f"line {line}: plays must be at least 1, got {plays}")
        if episode_id in seen:
            raise ResultError(f"line {line}: episode {episode_id} appears twice")
        seen.add(episode_id)
        items.append({"show_id": _text(row, "show_id", line), "episode_id": episode_id, "plays": plays})
    if len(items) > MAX_POPULAR:
        raise ResultError(f"POPULAR holds at most {MAX_POPULAR} episodes, got {len(items)}")
    return items


def recs_item(user_id: str, rows: list[dict[str, Any]], *, run_id: str, generated_at: int) -> dict[str, Any]:
    """One user's RECS item (§8.1)."""
    return {"PK": f"USER#{user_id}", "SK": "RECS", "rows": rows, "generated_at": generated_at, "run_id": run_id}


def popular_item(items: list[dict[str, Any]], *, run_id: str, generated_at: int) -> dict[str, Any]:
    """The POPULAR item (§8.1). Written even when empty: /home treats [] like a missing item."""
    return {"PK": "POPULAR", "SK": "GLOBAL", "items": items, "generated_at": generated_at, "run_id": run_id}


def result_key(uri: Any, bucket: str) -> str:
    """The S3 key of an Athena result, which must be ``s3://<lake>/recs-runs/...``."""
    prefix = f"s3://{bucket}/{RECS_RUNS_PREFIX}"
    if not isinstance(uri, str) or not uri.startswith(prefix) or len(uri) == len(prefix):
        raise ValueError(f"expected an Athena result under {prefix}, got {uri!r}")
    return uri.removeprefix(f"s3://{bucket}/")


def read_result(s3: Any, bucket: str, key: str) -> str:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Write one run's RECS and POPULAR items; returns ``{run_id, users_written, popular_count}`` (§10)."""
    run_id = event.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError(f"run_id must be a non-empty string, got {run_id!r}")
    bucket = required_env("LAKE_BUCKET")
    recs_key = result_key(event.get("recs_csv"), bucket)
    popular_key = result_key(event.get("popular_csv"), bucket)

    # Read and parse both results before writing anything (a bad file fails the run).
    s3 = boto3.client("s3")
    recs = parse_recs(read_result(s3, bucket, recs_key))
    popular = parse_popular(read_result(s3, bucket, popular_key))

    generated_at = clock.now_ms()
    table = boto3.resource("dynamodb").Table(required_env("TABLE_NAME"))
    # batch_writer sends 25 items per call and resends any DynamoDB returns as unprocessed.
    with table.batch_writer() as batch:
        for user_id, rows in recs.items():
            batch.put_item(Item=recs_item(user_id, rows, run_id=run_id, generated_at=generated_at))
    table.put_item(Item=popular_item(popular, run_id=run_id, generated_at=generated_at))

    log.emit_metrics({"RecsUsersWritten": len(recs)})
    log.log(
        "recs writer run complete",
        run_id=run_id,
        users_written=len(recs),
        recs_rows=sum(len(rows) for rows in recs.values()),
        popular_count=len(popular),
        recs_csv=recs_key,
        popular_csv=popular_key,
    )
    return {"run_id": run_id, "users_written": len(recs), "popular_count": len(popular)}

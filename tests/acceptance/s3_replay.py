"""S3 · Bad-input correctness (the replay test).

Owner: M4 · Tracker: M4-06 · Spec: CONTEXT §14 S3, §8.2, §11.
Generates 10,000 shuffled events with 10% duplicates, publishes them to the events topic,
then verifies progress and distinct-play counters in DynamoDB.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from acceptance.harness import Measurement
from boto3.dynamodb.conditions import Key
from simulator import DEFAULT_CATALOG
from simulator.generate import generate_events
from simulator.model import Catalog
from simulator.replay import replay

if TYPE_CHECKING:
    from acceptance.context import Context

EVENT_COUNT = 10_000
USER_COUNT = 100
DUPLICATE_RATE = 0.10
# Leave room for one SQS visibility-timeout retry after a slow Lambda batch.
PROCESSING_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5

CRITERION = "S3"
TITLE = "Bad-input correctness"
OWNER = "M4"
TARGET = "10k shuffled events with 10 % duplicates → 0 wrong positions, 0 double counts"


def _expected_progress(
    events: list[dict[str, Any]],
) -> dict[tuple[str, str], tuple[int, int, int, bool]]:
    expected = {}
    for event in events:
        key = (event["user_id"], event["episode_id"])
        client_ts = event["client_ts"]
        current = expected.get(key)
        if current is None or client_ts > current[0]:
            expected[key] = (
                client_ts,
                event["position_sec"],
                event["duration_sec"],
                event["event_type"] == "complete"
                or event["position_sec"] >= 0.95 * event["duration_sec"],
            )
    return expected


def _expected_plays(events: list[dict[str, Any]]) -> Counter[str]:
    unique_plays = {
        (event["episode_id"], event["event_id"])
        for event in events
        if event["event_type"] == "play"
    }
    return Counter(episode_id for episode_id, _ in unique_plays)


def _read_progress(ctx: Context, user_ids: list[str]) -> dict[tuple[str, str], dict[str, Any]]:
    table = ctx.session.resource("dynamodb").Table(ctx.cfg.table_name)
    items = {}
    for user_id in user_ids:
        query = {
            "KeyConditionExpression": Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("PROG#"),
            "ConsistentRead": True,
        }
        while True:
            response = table.query(**query)
            for item in response["Items"]:
                items[(user_id, item["episode_id"])] = item
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query["ExclusiveStartKey"] = last_key
    return items


def _read_trending(
    ctx: Context, event_date: str, episode_ids: set[str]
) -> dict[str, int]:
    client = ctx.client("dynamodb")
    keys = [
        {"PK": {"S": f"TREND#{event_date}"}, "SK": {"S": f"EP#{episode_id}"}}
        for episode_id in sorted(episode_ids)
    ]
    counts = {}
    for offset in range(0, len(keys), 100):
        pending = {ctx.cfg.table_name: {"Keys": keys[offset : offset + 100], "ConsistentRead": True}}
        for attempt in range(5):
            response = client.batch_get_item(RequestItems=pending)
            for item in response.get("Responses", {}).get(ctx.cfg.table_name, []):
                episode_id = item["SK"]["S"].removeprefix("EP#")
                counts[episode_id] = int(item["plays"]["N"])
            pending = response.get("UnprocessedKeys", {})
            if not pending:
                break
            if attempt < 4:
                time.sleep(0.1 * (2**attempt))
        else:
            raise RuntimeError("DynamoDB left trending keys unprocessed after five attempts")
    return counts


def _progress_mismatches(
    expected: dict[tuple[str, str], tuple[int, int, int, bool]],
    actual: dict[tuple[str, str], dict[str, Any]],
) -> list[tuple[str, str]]:
    mismatches = []
    for key, wanted in expected.items():
        item = actual.get(key)
        if item is None or (
            item["client_ts"],
            item["position_sec"],
            item["duration_sec"],
            item["completed"],
        ) != wanted:
            mismatches.append(key)
    mismatches.extend(key for key in actual.keys() - expected.keys())
    return mismatches


def run(ctx: Context) -> Measurement:
    run_id = uuid.uuid4().hex[:12]
    seed = int(run_id, 16)
    now_ms = time.time_ns() // 1_000_000
    events = generate_events(
        Catalog.load(DEFAULT_CATALOG),
        users=USER_COUNT,
        events=EVENT_COUNT,
        seed=seed,
        start_ms=now_ms - 2 * 60 * 60 * 1000,
        window_ms=60 * 60 * 1000,
        shuffle=True,
        dup_rate=DUPLICATE_RATE,
    )
    for event in events:
        event["user_id"] = f"sim-m4-s3-{run_id}-{event['user_id'].removeprefix('sim-')}"

    expected_progress = _expected_progress(events)
    expected_plays = _expected_plays(events)
    event_date = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).date().isoformat()
    user_ids = sorted({event["user_id"] for event in events})
    baseline_plays = _read_trending(ctx, event_date, set(expected_plays))

    report = replay(
        events,
        sns=ctx.client("sns"),
        topic_arn=ctx.cfg.events_topic_arn,
        now_fn=lambda: now_ms,
    )
    if report["failed_messages"] or report["skipped_invalid"] or report["published_events"] != EVENT_COUNT:
        return Measurement(
            False,
            "replay did not publish the complete generated dataset",
            {
                "run_id": run_id,
                "events": EVENT_COUNT,
                "published_events": report["published_events"],
                "failed_messages": report["failed_messages"],
                "skipped_invalid": report["skipped_invalid"],
            },
        )

    deadline = time.monotonic() + PROCESSING_TIMEOUT_SECONDS
    progress_mismatches = list(expected_progress)
    play_mismatches = list(expected_plays)
    while time.monotonic() < deadline:
        actual_progress = _read_progress(ctx, user_ids)
        actual_plays = _read_trending(ctx, event_date, set(expected_plays))
        progress_mismatches = _progress_mismatches(expected_progress, actual_progress)
        play_mismatches = [
            episode_id
            for episode_id, expected_count in expected_plays.items()
            if actual_plays.get(episode_id, 0) - baseline_plays.get(episode_id, 0) != expected_count
        ]
        if not progress_mismatches and not play_mismatches:
            return Measurement(
                True,
                f"0 wrong progress positions and 0 double-counted plays from {EVENT_COUNT} events",
                {
                    "run_id": run_id,
                    "events": EVENT_COUNT,
                    "unique_events": len({event["event_id"] for event in events}),
                    "progress_items": len(expected_progress),
                    "play_episodes": len(expected_plays),
                },
            )
        time.sleep(POLL_INTERVAL_SECONDS)

    return Measurement(
        False,
        f"{len(progress_mismatches)} progress mismatches and {len(play_mismatches)} play-count mismatches",
        {
            "run_id": run_id,
            "events": EVENT_COUNT,
            "progress_mismatches": progress_mismatches[:10],
            "play_mismatches": play_mismatches[:10],
        },
    )

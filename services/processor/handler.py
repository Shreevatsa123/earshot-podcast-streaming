"""Processor Lambda: SQS batch from the hot queue -> DynamoDB progress, trending, QoE (CONTEXT §8.2, §10).

Each SQS record's ``body`` is ``{"events": [...]}`` (CONTEXT §10 "Message format").

Owner: M4 · Tracker: M4-01..M4-04 · Function: ``earshot-<stage>-processor`` · Handler: ``processor.handler.main``
Env (CONTEXT §9): STAGE, TABLE_NAME, QOE_TOPIC_ARN, QOE_THRESHOLD.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared import clock, log
from shared.names import required_env


def decode_kinesis_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Decode a Kinesis record whose data is a JSON playback event."""
    data = base64.b64decode(record["kinesis"]["data"], validate=True)
    playback_event = json.loads(data)
    if not isinstance(playback_event, dict):
        raise ValueError("Kinesis record data must be a JSON object")
    return playback_event


def update_progress(
    table: Any,
    playback_event: Mapping[str, Any],
    *,
    updated_at_ms: int | None = None,
) -> bool:
    """Conditionally persist progress; return False when the event is stale."""
    client_ts = playback_event["client_ts"]
    completed = playback_event["event_type"] == "complete" or (
        playback_event["position_sec"] >= 0.95 * playback_event["duration_sec"]
    )
    try:
        table.update_item(
            Key={
                "PK": f"USER#{playback_event['user_id']}",
                "SK": f"PROG#{playback_event['episode_id']}",
            },
            UpdateExpression=(
                "SET #show_id = :show_id, #episode_id = :episode_id, "
                "#position_sec = :position_sec, #duration_sec = :duration_sec, "
                "#completed = :completed, #client_ts = :client_ts, "
                "#updated_at = :updated_at"
            ),
            ConditionExpression="attribute_not_exists(#client_ts) OR #client_ts < :client_ts",
            ExpressionAttributeNames={
                "#show_id": "show_id",
                "#episode_id": "episode_id",
                "#position_sec": "position_sec",
                "#duration_sec": "duration_sec",
                "#completed": "completed",
                "#client_ts": "client_ts",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":show_id": playback_event["show_id"],
                ":episode_id": playback_event["episode_id"],
                ":position_sec": playback_event["position_sec"],
                ":duration_sec": playback_event["duration_sec"],
                ":completed": completed,
                ":client_ts": client_ts,
                ":updated_at": clock.now_ms() if updated_at_ms is None else updated_at_ms,
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
    return True


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process a Kinesis batch, returning the event-source mapping response shape."""
    records = event.get("Records", [])
    stale_events = 0
    if records:
        table = boto3.resource("dynamodb").Table(required_env("TABLE_NAME"))
        for record in records:
            playback_event = decode_kinesis_record(record)
            if not update_progress(table, playback_event):
                stale_events += 1

    log.log("processor batch complete", records=len(records), stale_events=stale_events)
    log.emit_metrics({"StaleEvents": stale_events} if stale_events else {})
    return {"batchItemFailures": []}

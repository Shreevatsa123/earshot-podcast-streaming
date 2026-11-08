"""Processor Lambda: SQS batch from the hot queue -> DynamoDB progress, trending, QoE (CONTEXT §8.2, §10).

Each SQS record's ``body`` is ``{"events": [...]}`` (CONTEXT §10 "Message format").

Owner: M4 · Tracker: M4-01..M4-04 · Function: ``earshot-<stage>-processor`` · Handler: ``processor.handler.main``
Env (CONTEXT §9): STAGE, TABLE_NAME, QOE_TOPIC_ARN, QOE_THRESHOLD.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, HTTPClientError

from shared import clock, log
from shared.names import required_env

RETRYABLE_AWS_ERROR_CODES = frozenset(
    {
        "InternalServerError",
        "PriorRequestNotComplete",
        "ProvisionedThroughputExceededException",
        "RequestLimitExceeded",
        "RequestTimeout",
        "RequestTimeoutException",
        "ServiceUnavailable",
        "ThrottlingException",
        "TransactionConflictException",
    }
)

PROGRESS_EVENT_TYPES = frozenset({"play", "pause", "seek", "buffer", "heartbeat", "complete"})


def decode_sqs_message(record: Mapping[str, Any]) -> list[Any]:
    """Decode an SQS body containing a batch of playback events."""
    body = record.get("body")
    if not isinstance(body, str):
        raise ValueError("SQS message body must be a JSON object")
    try:
        message = json.loads(body)
    except json.JSONDecodeError as error:
        raise ValueError("SQS message body must be valid JSON") from error
    if not isinstance(message, dict) or not isinstance(message.get("events"), list):
        raise ValueError('SQS message body must contain an "events" array')
    return message["events"]


def is_progress_event(playback_event: Any) -> bool:
    """Return whether an event has the fields and types needed for progress writes."""
    if not isinstance(playback_event, Mapping):
        return False
    event_type = playback_event.get("event_type")
    position_sec = playback_event.get("position_sec")
    duration_sec = playback_event.get("duration_sec")
    return (
        isinstance(playback_event.get("user_id"), str)
        and isinstance(playback_event.get("show_id"), str)
        and isinstance(playback_event.get("episode_id"), str)
        and isinstance(event_type, str)
        and event_type in PROGRESS_EVENT_TYPES
        and all(
            type(playback_event.get(field)) is int
            for field in ("client_ts", "position_sec", "duration_sec")
        )
        and 0 <= position_sec <= 86400
        and duration_sec > 0
    )


def is_retryable_aws_error(error: BotoCoreError | ClientError) -> bool:
    """Identify AWS errors that should cause an SQS message retry."""
    if isinstance(error, HTTPClientError):
        return True
    if not isinstance(error, ClientError):
        return False
    code = error.response.get("Error", {}).get("Code")
    return code in RETRYABLE_AWS_ERROR_CODES


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
    """Process an SQS batch and report transient failures by message ID."""
    records = event.get("Records", [])
    stale_events = 0
    malformed_messages = 0
    malformed_events = 0
    batch_item_failures: list[dict[str, str]] = []
    failure_details: list[dict[str, str]] = []
    if records:
        table = boto3.resource("dynamodb").Table(required_env("TABLE_NAME"))
        for record in records:
            if not isinstance(record, Mapping):
                malformed_messages += 1
                continue
            message_id = record.get("messageId")
            try:
                playback_events = decode_sqs_message(record)
            except ValueError:
                malformed_messages += 1
                continue
            if not isinstance(message_id, str) or not message_id:
                malformed_messages += 1
                continue

            for playback_event in playback_events:
                if not is_progress_event(playback_event):
                    malformed_events += 1
                    continue
                try:
                    if not update_progress(table, playback_event):
                        stale_events += 1
                except (BotoCoreError, ClientError) as error:
                    if not is_retryable_aws_error(error):
                        raise
                    batch_item_failures.append({"itemIdentifier": message_id})
                    error_code = (
                        error.response.get("Error", {}).get("Code")
                        if isinstance(error, ClientError)
                        else type(error).__name__
                    )
                    failure_details.append({"messageId": message_id, "error": str(error_code)})
                    break

    log.log(
        "processor batch complete",
        records=len(records),
        stale_events=stale_events,
        malformed_messages=malformed_messages,
        malformed_events=malformed_events,
        failed_messages=failure_details,
    )
    log.emit_metrics({"StaleEvents": stale_events} if stale_events else {})
    return {"batchItemFailures": batch_item_failures}

"""Archiver Lambda: SQS batch from the cold queue -> gzipped JSON Lines in the S3 lake (CONTEXT §9, §10).

Replaces Amazon Data Firehose. Each SQS record's ``body`` is ``{"events": [...]}``
(CONTEXT §10 "Message format").

Owner: M5 · Tracker: M5-02 · Function: ``earshot-<stage>-archiver`` · Handler: ``archiver.handler.main``
Env (CONTEXT §9): STAGE, LAKE_BUCKET.

For each batch:
- events are grouped by the UTC hour of ``server_ts`` and written as one gzipped JSON
  Lines object per hour: ``events/dt=YYYY-MM-DD/hour=HH/<uuid>.json.gz``, one §6 event
  per line with exactly the §6 fields;
- a message that can't be decoded is reported as failed on its own, so after 5 receives
  it lands in the DLQ (alarmed) instead of silently missing from the lake;
- an event without every §6 field or a usable ``server_ts`` is skipped and counted: it
  has no folder to go to;
- if any S3 write fails, every message in the batch is reported as failed (§10). The
  retry may write some events twice, which is fine: every query counts DISTINCT event_id.

The archiver emits no custom metric (§10 has none for it). It logs one JSON line per
batch; a write failure is logged at ERROR level.
"""

from __future__ import annotations

import gzip
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from shared import log
from shared.names import LAKE_EVENTS_PREFIX, required_env
from shared.validate import EVENT_FIELDS


@dataclass
class BatchPlan:
    """What one SQS batch turns into, before anything is written."""

    #: Hour folder (``dt=YYYY-MM-DD/hour=HH``) -> JSON lines for that hour.
    lines_by_folder: dict[str, list[str]] = field(default_factory=dict)
    #: Every message ID in the batch, so a failed write can report them all.
    message_ids: list[str] = field(default_factory=list)
    #: Messages whose body couldn't be decoded: reported as failed on their own.
    malformed_message_ids: list[str] = field(default_factory=list)
    #: Records with no messageId at all: nothing to report, so only counted.
    unidentified_records: int = 0
    events: int = 0
    skipped_events: int = 0


def decode_message(record: Mapping[str, Any]) -> list[Any]:
    """The ``events`` list of one SQS record; ``ValueError`` if the body isn't ``{"events": [...]}``."""
    body = record.get("body")
    if not isinstance(body, str):
        raise ValueError("SQS message body must be a JSON string")
    try:
        message = json.loads(body)
    except json.JSONDecodeError as error:
        raise ValueError("SQS message body must be valid JSON") from error
    if not isinstance(message, dict) or not isinstance(message.get("events"), list):
        raise ValueError('SQS message body must contain an "events" array')
    return message["events"]


def hour_folder(server_ts_ms: int) -> str:
    """The lake folder for an event: ``dt=YYYY-MM-DD/hour=HH`` of its ``server_ts`` in UTC."""
    at = datetime.fromtimestamp(server_ts_ms / 1000, tz=timezone.utc)
    return f"dt={at:%Y-%m-%d}/hour={at:%H}"


def lake_line(event: Any) -> tuple[str, str] | None:
    """``(folder, JSON line)`` for one event, or None if it can't go in the lake.

    The line holds exactly the §6 fields in contract order; anything else is dropped. An
    event missing a §6 field is rejected rather than written with a gap, because Athena
    would read the gap as NULL without any error.
    """
    if not isinstance(event, Mapping) or any(name not in event for name in EVENT_FIELDS):
        return None
    server_ts = event["server_ts"]
    if not isinstance(server_ts, int) or isinstance(server_ts, bool) or server_ts <= 0:
        return None
    line = json.dumps({name: event[name] for name in EVENT_FIELDS}, separators=(",", ":"))
    return hour_folder(server_ts), line


def plan_batch(records: list[Any]) -> BatchPlan:
    """Decode an SQS batch and group its events into lake folders. No AWS calls."""
    plan = BatchPlan()
    for record in records:
        message_id = record.get("messageId") if isinstance(record, Mapping) else None
        if not isinstance(message_id, str) or not message_id:
            plan.unidentified_records += 1
            continue
        plan.message_ids.append(message_id)
        try:
            events = decode_message(record)
        except ValueError:
            plan.malformed_message_ids.append(message_id)
            continue
        for event in events:
            placed = lake_line(event)
            if placed is None:
                plan.skipped_events += 1
                continue
            folder, line = placed
            plan.lines_by_folder.setdefault(folder, []).append(line)
            plan.events += 1
    return plan


def object_key(folder: str, name: str) -> str:
    """S3 key for one file: ``events/dt=YYYY-MM-DD/hour=HH/<name>.json.gz``."""
    return f"{LAKE_EVENTS_PREFIX}{folder}/{name}.json.gz"


def encode_lines(lines: list[str]) -> bytes:
    """Gzipped JSON Lines: one object per line, newline-terminated."""
    return gzip.compress(("\n".join(lines) + "\n").encode("utf-8"))


def write_files(s3: Any, bucket: str, plan: BatchPlan) -> int:
    """Write one ``.json.gz`` object per hour folder; returns how many were written.

    No ``ContentEncoding`` header: Athena decompresses by the ``.gz`` extension, and the
    header makes some download tools unzip the file on the way.
    """
    written = 0
    for folder, lines in plan.lines_by_folder.items():
        s3.put_object(Bucket=bucket, Key=object_key(folder, str(uuid.uuid4())), Body=encode_lines(lines))
        written += 1
    return written


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Archive an SQS batch and report failed messages by ID (CONTEXT §10)."""
    records = event.get("Records", [])
    plan = plan_batch(records if isinstance(records, list) else [])
    failed_ids = list(plan.malformed_message_ids)
    files_written = 0
    write_error: str | None = None
    if plan.lines_by_folder:
        try:
            files_written = write_files(boto3.client("s3"), required_env("LAKE_BUCKET"), plan)
        except (BotoCoreError, ClientError) as error:
            # §10: one failed write fails the whole batch. Files already written stay;
            # the retry writes their events again, and the queries count DISTINCT event_id.
            failed_ids = list(plan.message_ids)
            write_error = (
                error.response.get("Error", {}).get("Code", "ClientError")
                if isinstance(error, ClientError)
                else type(error).__name__
            )

    log.log(
        "archiver batch complete",
        level="ERROR" if write_error else "INFO",
        records=len(plan.message_ids) + plan.unidentified_records,
        events=plan.events,
        files_written=files_written,
        folders=sorted(plan.lines_by_folder),
        skipped_events=plan.skipped_events,
        malformed_messages=plan.malformed_message_ids,
        unidentified_records=plan.unidentified_records,
        write_error=write_error,
        failed_messages=len(failed_ids),
    )
    return {"batchItemFailures": [{"itemIdentifier": message_id} for message_id in failed_ids]}

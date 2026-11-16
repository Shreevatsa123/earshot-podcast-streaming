"""``simulator replay --direct``: publish a JSON Lines file straight to the SNS events topic.

This skips the API and ingest, so it needs no Cognito user: only AWS credentials allowed
to publish on ``earshot-<stage>-events`` (the simulator instance's role has that).

- Events go out in file order, 25 per SNS message, in the §10 message format
  ``{"events": [...]}``, sent with ``PublishBatch`` (10 messages per call).
- Each event is checked with ``shared.validate`` and must have a ``sim-`` ``user_id``;
  invalid lines are skipped and counted in the report.
- ``server_ts`` is set to the publish time (as ingest would), unless ``--keep-server-ts``.
  Duplicates in the file are sent as they are: that's the point of the S3 test.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from typing import Any

from shared import clock
from shared.validate import order_fields, validate_event

EVENTS_PER_MESSAGE = 25
MESSAGES_PER_CALL = 10
MAX_ATTEMPTS = 4
BACKOFF_SEC = (0.1, 0.2, 0.4)


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def prepare(raw_events: list[Any], *, now_ms: int, keep_server_ts: bool) -> tuple[list[dict[str, Any]], int]:
    """Validate and enrich events. Returns ``(events, skipped)``."""
    ready: list[dict[str, Any]] = []
    skipped = 0
    for raw in raw_events:
        clean, _reason = validate_event(raw, now_ms=now_ms)
        user = raw.get("user_id") if isinstance(raw, dict) else None
        if clean is None or not (isinstance(user, str) and user.startswith("sim-")):
            skipped += 1
            continue
        clean["user_id"] = user
        server_ts = raw.get("server_ts")
        keep = keep_server_ts and isinstance(server_ts, int) and not isinstance(server_ts, bool)
        clean["server_ts"] = server_ts if keep else now_ms
        ready.append(order_fields(clean))
    return ready, skipped


def replay(
    raw_events: list[Any],
    *,
    sns: Any,
    topic_arn: str,
    keep_server_ts: bool = False,
    now_fn: Callable[[], int] = clock.now_ms,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Publish the events and return a report."""
    started = now_fn()
    events, skipped = prepare(raw_events, now_ms=started, keep_server_ts=keep_server_ts)
    messages = [json.dumps({"events": chunk}, separators=(",", ":")) for chunk in _chunks(events, EVENTS_PER_MESSAGE)]
    failed_messages = 0
    published_events = 0

    for call in _chunks(list(enumerate(messages)), MESSAGES_PER_CALL):
        pending = {f"m{index}": body for index, body in call}
        for attempt in range(MAX_ATTEMPTS):
            if not pending:
                break
            try:
                response = sns.publish_batch(
                    TopicArn=topic_arn,
                    PublishBatchRequestEntries=[{"Id": key, "Message": body} for key, body in pending.items()],
                )
                for ok in response.get("Successful", []):
                    body = pending.pop(ok["Id"], None)
                    if body is not None:
                        published_events += len(json.loads(body)["events"])
            except Exception as error:  # noqa: BLE001
                if attempt == MAX_ATTEMPTS - 1:
                    print(f"publish failed: {error!r}")
            if pending and attempt < MAX_ATTEMPTS - 1:
                sleep(BACKOFF_SEC[attempt])
        failed_messages += len(pending)

    return {
        "topic_arn": topic_arn,
        "start_ms": started,
        "end_ms": now_fn(),
        "lines": len(raw_events),
        "skipped_invalid": skipped,
        "messages": len(messages),
        "failed_messages": failed_messages,
        "published_events": published_events,
    }

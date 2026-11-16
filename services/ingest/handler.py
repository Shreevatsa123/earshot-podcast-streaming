"""Ingest Lambda: ``POST /events`` -> the SNS events topic (CONTEXT §7.5, §10 "Message format").

Owner: M3 · Tracker: M3-02 · Function: ``earshot-<stage>-ingest`` · Handler: ``ingest.handler.main``
Env (CONTEXT §9): STAGE, TOPIC_ARN, ALLOWED_GENRES.

Per request:
1. 400 if the body isn't JSON, isn't ``{"events": [...]}``, has 0 or > 25 events, or is
   bigger than 64 KB.
2. Validate each event (``shared.validate``) and apply the identity rule (§7.2):
   simulator callers keep a ``sim-`` ``user_id``, everyone else gets the token ``sub``.
3. Stamp ``server_ts`` (the same value for the whole request) and ``schema_version``.
4. Publish **one** SNS message ``{"events": [...]}`` with every accepted event. On a
   throttling or transient error, retry 3 times (50/100/200 ms). If it still fails, every
   event in the request is rejected as ``THROTTLED`` so the client retries it.
5. 202 ``{"accepted": n, "rejected": [{"index", "reason"}]}`` + ``EventsAccepted`` and
   ``EventsRejected`` metrics.
"""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Mapping
from typing import Any

from shared import clock, http, log
from shared.validate import DEFAULT_GENRES, validate_event

MAX_EVENTS = 25
MAX_BODY_BYTES = 64 * 1024
SIM_USER_PREFIX = "sim-"
PUBLISH_BACKOFF_SEC = (0.05, 0.1, 0.2)

#: Error codes worth retrying (throttling, or AWS having a bad moment).
RETRYABLE_ERROR_CODES = frozenset(
    {
        "Throttling",
        "ThrottlingException",
        "ThrottledException",
        "TooManyRequestsException",
        "RequestLimitExceeded",
        "InternalError",
        "InternalFailure",
        "ServiceUnavailable",
        "RequestTimeout",
    }
)

_sns_client: Any = None


def _sns() -> Any:
    """The SNS client, created once per container (boto3 is imported lazily for tests)."""
    global _sns_client
    if _sns_client is None:
        import boto3

        _sns_client = boto3.client("sns")
    return _sns_client


def _allowed_genres() -> tuple[str, ...]:
    raw = os.environ.get("ALLOWED_GENRES", "")
    genres = tuple(g.strip() for g in raw.split(",") if g.strip())
    return genres or DEFAULT_GENRES


def _error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if isinstance(response, Mapping):
        return (response.get("Error") or {}).get("Code")
    return None


def _is_retryable(error: Exception) -> bool:
    code = _error_code(error)
    if code is not None:
        return code in RETRYABLE_ERROR_CODES
    # No AWS error code: a network problem (timeout, connection reset). Worth retrying.
    return True


def publish_events(topic_arn: str, events: list[dict[str, Any]]) -> None:
    """Publish one ``{"events": [...]}`` message, retrying throttling/transient errors.

    Raises the last error if every attempt fails.
    """
    message = json.dumps({"events": events}, separators=(",", ":"))
    attempts = len(PUBLISH_BACKOFF_SEC) + 1
    for attempt in range(attempts):
        try:
            _sns().publish(TopicArn=topic_arn, Message=message)
            return
        except Exception as error:  # noqa: BLE001 - botocore isn't imported at module level
            if attempt == attempts - 1 or not _is_retryable(error):
                raise
            time.sleep(PUBLISH_BACKOFF_SEC[attempt])


def _body_bytes(event: Mapping[str, Any]) -> int:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        try:
            return len(base64.b64decode(raw))
        except ValueError:
            return 0
    return len(raw.encode("utf-8"))


def _bad_request(message: str) -> dict[str, Any]:
    log.log("bad request", level="WARN", reason=message)
    return http.error_response("BAD_REQUEST", message)


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    claims = http.jwt_claims(event)
    sub = claims.get("sub")
    if not sub:
        # The JWT authorizer should make this impossible; fail closed anyway.
        return http.error_response("UNAUTHORIZED", "Missing token subject")

    if _body_bytes(event) > MAX_BODY_BYTES:
        return _bad_request(f"Body is larger than {MAX_BODY_BYTES} bytes")
    try:
        body = http.parse_json_body(event)
    except (ValueError, UnicodeDecodeError):
        return _bad_request("Body must be JSON")
    if not isinstance(body, dict) or not isinstance(body.get("events"), list):
        return _bad_request('Body must be {"events": [...]}')
    raw_events = body["events"]
    if not 1 <= len(raw_events) <= MAX_EVENTS:
        return _bad_request(f"Send between 1 and {MAX_EVENTS} events per request")

    now = clock.now_ms()
    simulator = http.is_simulator(claims)
    genres = _allowed_genres()
    accepted: list[dict[str, Any]] = []
    accepted_indexes: list[int] = []
    rejected: list[dict[str, Any]] = []

    for index, raw in enumerate(raw_events):
        clean, reason = validate_event(raw, now_ms=now, allowed_genres=genres)
        if clean is None:
            rejected.append({"index": index, "reason": reason})
            continue
        if simulator:
            user_id = raw.get("user_id")
            if not (isinstance(user_id, str) and user_id.startswith(SIM_USER_PREFIX) and len(user_id) <= 64):
                rejected.append({"index": index, "reason": "FORBIDDEN_USER"})
                continue
        else:
            user_id = sub
        clean["user_id"] = user_id
        clean["server_ts"] = now
        accepted.append(clean)
        accepted_indexes.append(index)

    if accepted:
        try:
            publish_events(os.environ["TOPIC_ARN"], accepted)
        except Exception as error:  # noqa: BLE001
            log.log("publish failed", level="ERROR", error=repr(error), events=len(accepted))
            rejected.extend({"index": i, "reason": "THROTTLED"} for i in accepted_indexes)
            rejected.sort(key=lambda item: item["index"])
            accepted = []

    reasons: dict[str, int] = {}
    for item in rejected:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    log.log(
        "events ingested",
        received=len(raw_events),
        accepted=len(accepted),
        rejected=len(rejected),
        reasons=reasons,
        simulator=simulator,
    )
    log.emit_metrics({"EventsAccepted": len(accepted), "EventsRejected": len(rejected)})
    return http.json_response(202, {"accepted": len(accepted), "rejected": rejected})

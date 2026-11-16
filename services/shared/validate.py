"""Playback event validation (CONTEXT §6, §7.5).

Owner: M3 · Tracker: M3-01. Lives in shared/ because M4's replay test and the simulator
use the same rules.

``validate_event`` checks the fields a client sends. It does **not** check ``user_id`` or
``server_ts``: ingest sets both itself (identity rule §7.2, ``server_ts`` §6), so the
returned clean event never contains them and the caller adds them.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from typing import Any

EVENT_TYPES = ("play", "pause", "seek", "buffer", "heartbeat", "complete")
REGIONS = ("us-east", "us-west", "eu-west", "ap-south")
DEVICES = ("web", "sim")

MIN_CLIENT_TS_MS = 1_767_225_600_000  # 2026-01-01T00:00:00Z
MAX_CLIENT_SKEW_MS = 300_000  # client_ts may be at most 5 minutes in the future
MAX_POSITION_SEC = 86_400
SCHEMA_VERSION = 1
MAX_ID_LENGTH = 64

#: Every §6 field in contract order. The archiver writes exactly these (CONTEXT §9).
EVENT_FIELDS = (
    "event_id",
    "schema_version",
    "user_id",
    "session_id",
    "show_id",
    "episode_id",
    "genre",
    "event_type",
    "position_sec",
    "duration_sec",
    "client_ts",
    "server_ts",
    "region",
    "device",
)

_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)

# The default genre list (CONTEXT §8.3). Kept as a literal so this module needs no imports
# from the rest of shared/; tests check it matches names.GENRES.
DEFAULT_GENRES = ("true-crime", "comedy", "news", "technology", "business", "science", "sports", "history")


def is_uuid4(value: Any) -> bool:
    """True for a UUID v4 string (either case)."""
    return isinstance(value, str) and bool(_UUID4_RE.match(value))


def _as_int(value: Any) -> int | None:
    """An int, or a float with no fractional part (JSON from browsers). Bools are not ints."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _is_id(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_ID_LENGTH


def validate_event(
    raw: Mapping[str, Any] | Any,
    *,
    now_ms: int,
    allowed_genres: Collection[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one client event against CONTEXT §6.

    Returns ``(clean_event, None)`` if valid, otherwise ``(None, reason)`` where ``reason``
    is ``INVALID_JSON`` (not a JSON object) or ``INVALID_FIELD:<name>`` for the first bad
    field, checked in §6 order.

    The clean event has the §6 fields except ``user_id`` and ``server_ts`` (the caller sets
    those), with ``schema_version`` defaulted to 1. Unknown fields are dropped.
    """
    if not isinstance(raw, Mapping):
        return None, "INVALID_JSON"
    genres = allowed_genres if allowed_genres is not None else DEFAULT_GENRES

    def bad(field: str) -> tuple[None, str]:
        return None, f"INVALID_FIELD:{field}"

    if not is_uuid4(raw.get("event_id")):
        return bad("event_id")

    schema_version = raw.get("schema_version", SCHEMA_VERSION)
    if schema_version is None:
        schema_version = SCHEMA_VERSION
    if _as_int(schema_version) != SCHEMA_VERSION:
        return bad("schema_version")

    if not is_uuid4(raw.get("session_id")):
        return bad("session_id")
    if not _is_id(raw.get("show_id")):
        return bad("show_id")
    if not _is_id(raw.get("episode_id")):
        return bad("episode_id")
    if raw.get("genre") not in genres:
        return bad("genre")
    if raw.get("event_type") not in EVENT_TYPES:
        return bad("event_type")

    position = _as_int(raw.get("position_sec"))
    if position is None or not 0 <= position <= MAX_POSITION_SEC:
        return bad("position_sec")

    duration = _as_int(raw.get("duration_sec"))
    if duration is None or duration <= 0:
        return bad("duration_sec")

    client_ts = _as_int(raw.get("client_ts"))
    if client_ts is None or not MIN_CLIENT_TS_MS <= client_ts <= now_ms + MAX_CLIENT_SKEW_MS:
        return bad("client_ts")

    if raw.get("region") not in REGIONS:
        return bad("region")
    if raw.get("device") not in DEVICES:
        return bad("device")

    clean = {
        "event_id": raw["event_id"],
        "schema_version": SCHEMA_VERSION,
        "session_id": raw["session_id"],
        "show_id": raw["show_id"],
        "episode_id": raw["episode_id"],
        "genre": raw["genre"],
        "event_type": raw["event_type"],
        "position_sec": position,
        "duration_sec": duration,
        "client_ts": client_ts,
        "region": raw["region"],
        "device": raw["device"],
    }
    return clean, None


def order_fields(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return the event with its §6 fields in contract order (nice for files and logs)."""
    return {field: event[field] for field in EVENT_FIELDS if field in event}

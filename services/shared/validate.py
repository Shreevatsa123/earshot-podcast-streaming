"""Playback event validation (CONTEXT §6, §7.5).

Owner: M3 · Tracker: M3-01. Lives in shared/ because M4's replay test uses the same rules.

STATUS: STUB. The constants below come straight from CONTEXT §6. M3 implements
``validate_event`` (and may refine its signature before anyone depends on it).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

EVENT_TYPES = ("play", "pause", "seek", "buffer", "heartbeat", "complete")
REGIONS = ("us-east", "us-west", "eu-west", "ap-south")
DEVICES = ("web", "sim")

MIN_CLIENT_TS_MS = 1_767_225_600_000  # 2026-01-01T00:00:00Z
MAX_CLIENT_SKEW_MS = 300_000  # client_ts may be at most 5 minutes in the future
MAX_POSITION_SEC = 86_400
SCHEMA_VERSION = 1


def validate_event(
    raw: Mapping[str, Any], *, now_ms: int
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one event.

    Returns ``(clean_event, None)`` if valid, otherwise ``(None, reason)`` where ``reason``
    is ``INVALID_JSON`` or ``INVALID_FIELD:<name>`` (CONTEXT §7.5).
    """
    raise NotImplementedError("M3-01: implement the CONTEXT §6 validation rules")

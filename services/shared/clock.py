"""Time helpers. All timestamps in the system are epoch milliseconds, UTC (CONTEXT §6)."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def now_ms() -> int:
    """Current time in epoch milliseconds. Patch this in tests to freeze time."""
    return time.time_ns() // 1_000_000


def _utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms // 1000, tz=timezone.utc)


def utc_date(ms: int) -> str:
    """``YYYY-MM-DD`` in UTC, e.g. the trending key date (CONTEXT §8.1)."""
    return _utc(ms).strftime("%Y-%m-%d")


def utc_minute(ms: int) -> str:
    """``yyyymmddHHMM`` in UTC, e.g. the QoE window key (CONTEXT §8.1)."""
    return _utc(ms).strftime("%Y%m%d%H%M")

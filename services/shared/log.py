"""Structured JSON logs and CloudWatch metrics for Lambdas (CONTEXT §0 rule 8, §10).

Metrics use the Embedded Metric Format: a specially shaped JSON log line that CloudWatch
turns into a metric, so no extra API calls or permissions are needed.

Log once per batch or request, not once per event.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from shared.clock import now_ms

NAMESPACE = "Earshot"

#: The only custom metrics allowed (CONTEXT §10). Each extra metric costs money, so
#: adding one is a CONTEXT change first.
ALLOWED_METRICS = frozenset(
    {
        "EventsAccepted",
        "EventsRejected",
        "PlaysCounted",
        "DuplicateEvents",
        "StaleEvents",
        "QoEAlertsSent",
        "HomeFallback",
        "RecsUsersWritten",
    }
)


def log(message: str, *, level: str = "INFO", **fields: Any) -> None:
    """Print one JSON log line, e.g. ``log("batch done", records=100, failed=0)``."""
    line = {"level": level, "message": message, "ts": now_ms(), **fields}
    print(json.dumps(line, default=str), flush=True)


def emit_metrics(values: Mapping[str, float], *, unit: str = "Count") -> dict[str, Any]:
    """Publish custom metrics with the single ``Stage`` dimension (CONTEXT §10).

    Example: ``emit_metrics({"EventsAccepted": 24, "EventsRejected": 1})``.
    Returns the log document, which makes it easy to check in tests.
    """
    unknown = sorted(set(values) - ALLOWED_METRICS)
    if unknown:
        raise ValueError(
            f"Metrics {unknown} aren't in CONTEXT §10. Custom metrics cost money; "
            "propose a CONTEXT change before adding one."
        )
    document: dict[str, Any] = {
        "_aws": {
            "Timestamp": now_ms(),
            "CloudWatchMetrics": [
                {
                    "Namespace": NAMESPACE,
                    "Dimensions": [["Stage"]],
                    "Metrics": [{"Name": name, "Unit": unit} for name in values],
                }
            ],
        },
        "Stage": os.environ.get("STAGE", "unknown"),
        **values,
    }
    if values:
        print(json.dumps(document), flush=True)
    return document

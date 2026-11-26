"""S6 · API performance.

Owner: M6 + M2 · Tracker: M6-06 · Spec: CONTEXT §14 S6.
Test method: Locust from the EC2 instance, 50 users calling ``GET /home`` for 5 minutes
(``tests/load/locustfile.py``, its docstring has the runbook). Copy Locust's
``s6_stats.csv`` into ``tests/load/output/s6_stats.csv`` (or set ``S6_STATS_CSV``), then run
this check. Pass if p95 < 500 ms and errors < 1 %.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from acceptance.harness import REPO_ROOT, Measurement
from load.home_load import parse_stats

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S6"
TITLE = "API performance"
OWNER = "M6 + M2"
TARGET = "/home p95 < 500 ms at 50 concurrent users, < 1 % errors (Locust from EC2)"

DEFAULT_STATS = REPO_ROOT / "tests" / "load" / "output" / "s6_stats.csv"


def stats_path() -> Path:
    return Path(os.environ.get("S6_STATS_CSV") or DEFAULT_STATS)


def run(ctx: Context) -> Measurement:
    path = stats_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} doesn't exist. Run the Locust test on EC2 first and copy s6_stats.csv here "
            "(runbook in tests/load/locustfile.py)"
        )
    result = parse_stats(path.read_text(encoding="utf-8"))
    taken = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M")
    return Measurement(
        passed=result.passed,
        measured=f"{result.summary()}; Locust results saved {taken} UTC",
        details={
            "requests": result.requests,
            "failures": result.failures,
            "p95_ms": result.p95_ms,
            "error_rate_pct": round(result.error_rate_pct, 3),
            "stats_file": str(path),
        },
    )

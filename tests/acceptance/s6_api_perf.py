"""S6 · API performance.

Owner: M6 + M2 · Tracker: M6-06 · Spec: CONTEXT §14 S6.
Test method: Locust from the EC2 instance, 50 users calling ``GET /home`` for 5 minutes.
Read p95 latency and the error rate from Locust's CSV output. Pass if p95 < 500 ms and
errors < 1 %.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S6"
TITLE = "API performance"
OWNER = "M6 + M2"
TARGET = "/home p95 < 500 ms at 50 concurrent users, < 1 % errors (Locust from EC2)"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M6/M2: needs /home (M2-06) and Locust on EC2 (M6-06)")

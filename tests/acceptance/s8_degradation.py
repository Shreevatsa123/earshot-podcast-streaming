"""S8 · Graceful degradation.

Owner: M2 · Spec: CONTEXT §14 S8, §7.4 rule 4, §9 flags.
Test method: set ``recs_enabled=false`` and ``recs_fault_injection=true`` (scripts/set_flag.py),
wait 10 s for the flags cache, call ``GET /home`` repeatedly, then restore the flags (in a
``finally``). Pass if there are 0 responses with status >= 500 and every body has
``"degraded": true``.

The flags go back to exactly what they were before the check. The API may serve the fault
flags for up to 10 s more after that (its cache), so wait 10 s before checking /home by hand.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import TYPE_CHECKING

from set_flag import update_flags

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S8"
TITLE = "Graceful degradation"
OWNER = "M2"
TARGET = "recs_enabled=false and recs_fault_injection=true → /home 0 × 5xx, degraded:true"

FAULT_FLAGS = {"recs_enabled": False, "recs_fault_injection": True}
CACHE_WAIT_S = 11  # the API caches the flags for 10 s (§9), plus a margin
CALLS = 20


def run(ctx: Context) -> Measurement:
    ssm, parameter = ctx.client("ssm"), ctx.cfg.ssm_flags
    before, _ = update_flags(ssm, parameter, FAULT_FLAGS)
    try:
        time.sleep(CACHE_WAIT_S)
        # Different virtual users, so the check isn't about one user's data (§7.2 header).
        responses = [ctx.api.get("/home", sim_user=f"sim-{i:06d}") for i in range(CALLS)]
    finally:
        update_flags(ssm, parameter, before)

    statuses = Counter(r.status for r in responses)
    server_errors = sum(n for status, n in statuses.items() if status >= 500)
    degraded = sum(1 for r in responses if isinstance(r.body, dict) and r.body.get("degraded") is True)
    latencies = sorted(r.elapsed_ms for r in responses)
    return Measurement(
        passed=server_errors == 0 and degraded == CALLS,
        measured=f"{server_errors} × 5xx, {degraded}/{CALLS} degraded:true",
        details={
            "statuses": {str(s): n for s, n in sorted(statuses.items())},
            "median_ms": latencies[len(latencies) // 2],
            "max_ms": latencies[-1],
            "flags_restored_to": before,
        },
    )

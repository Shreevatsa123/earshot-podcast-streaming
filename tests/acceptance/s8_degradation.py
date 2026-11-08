"""S8 · Graceful degradation.

Owner: M2 · Spec: CONTEXT §14 S8, §7.4 rule 4, §9 flags.
Test method: set ``recs_enabled=false`` and ``recs_fault_injection=true`` (scripts/set_flag.py),
wait 10 s for the flags cache, call ``GET /home`` repeatedly, then restore the flags (in a
``finally``). Pass if there are 0 responses with status >= 500 and every body has
``"degraded": true``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S8"
TITLE = "Graceful degradation"
OWNER = "M2"
TARGET = "recs_enabled=false and recs_fault_injection=true → /home 0 × 5xx, degraded:true"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M2: write this check (see the docstring)")

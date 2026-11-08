"""S10 · Cost and automation.

Owner: M6 · Spec: CONTEXT §14 S10.

Automated here: after ``make pipeline-down``, nothing hourly-billed is left running in the
account (the same checks as ``make cost-check``). Run it only while the pipeline is down.

Recorded by hand in docs/results.md ("S10 notes"): the semester cost from the Billing
console, how long ``make pipeline-up`` takes, and a full deploy from scratch.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from acceptance.harness import Measurement
from cost_check import Clients, run_checks

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S10"
TITLE = "Cost and automation"
OWNER = "M6"
TARGET = (
    "Semester < $30; pipeline-up < 10 min; full deploy from scratch < 25 min; "
    "after pipeline-down, 0 hourly-billed resources"
)


def run(ctx: Context) -> Measurement:
    findings, failures = run_checks(Clients.from_factory(ctx.client))
    if failures:
        raise RuntimeError("the cost check couldn't run fully: " + "; ".join(failures))
    hourly = [f for f in findings if f.hourly]
    measured = f"{len(hourly)} hourly-billed resources running"
    if hourly:
        measured += " (" + ", ".join(f"{f.kind} {f.name}" for f in hourly) + ")"
    measured += "; cost and deploy times: see S10 notes"
    return Measurement(
        passed=not hourly,
        measured=measured,
        details={"hourly": [asdict(f) for f in hourly], "leftovers": [asdict(f) for f in findings if not f.hourly]},
    )

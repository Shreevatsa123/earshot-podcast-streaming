"""S10 · Cost and automation.

Owner: M6 · Tracker: M6-08 · Spec: CONTEXT §14 S10.

To automate (M6-08): after ``make pipeline-down``, nothing hourly-billed is left running in
the account, using the same checks as the cost check script. Run it only while the pipeline
is down.

Recorded by hand in docs/results.md ("S10 notes"): the semester cost from the Billing
console, how long ``make pipeline-up`` takes, and a full deploy from scratch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

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
    raise NotImplementedError("M6: needs the cost check script (M6-08)")

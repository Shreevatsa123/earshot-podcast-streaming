"""S4 · Throughput with no data loss.

Owner: M3 + M6 · Spec: CONTEXT §14 S4, §7.5 ("lost event"), §11 (run report).
Test method: run the simulator on EC2 at 500 events/s for 10 min, then compare three
counts for that run: ``accepted`` in the simulator's run report, events processed
(``EventsAccepted`` vs processor metrics in CloudWatch), and distinct ``event_id`` in Athena
for the run's time window. Pass if all three match (0 lost).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S4"
TITLE = "Throughput, no loss"
OWNER = "M3 + M6"
TARGET = "500 events/s for 10 min; accepted = processed = stored (Athena distinct count)"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M3/M6: needs the simulator on EC2 (M3-06, M3-07)")

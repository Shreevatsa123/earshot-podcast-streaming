"""S9 · Quality alerting.

Owner: M4 + M3 · Spec: CONTEXT §14 S9, §8.2 (QoE), §11 (``--mode buffer-storm``).
Test method: run the simulator in buffer-storm mode for one region and note the start
time. The alert is an email, so this one is partly manual: automate the storm and the
``QoEAlertsSent`` metric check, then record the email's arrival time by hand in
docs/results.md. Pass if the email arrives < 2 min after the storm starts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S9"
TITLE = "Quality alerting"
OWNER = "M4 + M3"
TARGET = "Buffer storm in one region → SNS email < 2 min"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M4/M3: needs buffer-storm mode (M3-08) and QoE alerts (M4-03)")

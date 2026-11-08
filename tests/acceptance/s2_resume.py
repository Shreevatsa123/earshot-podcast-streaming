"""S2 · Resume freshness and accuracy.

Owner: M4 + M1 · Spec: CONTEXT §14 S2, §8.2 (progress writes).
Test method: 20 timed trials. Send a ``pause`` event for a sim user (``ctx.api.post``),
then poll ``GET /progress/{episodeId}`` until the position appears. Pass if the p95 delay
is under 5 s and every stored position is within ±2 s of the one sent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S2"
TITLE = "Resume freshness and accuracy"
OWNER = "M4 + M1"
TARGET = "Visible in API < 5 s after pause (p95 of 20 trials); resume within ±2 s"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M4/M1: write this check (see the docstring)")

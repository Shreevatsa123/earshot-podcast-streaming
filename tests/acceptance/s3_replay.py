"""S3 · Bad-input correctness (the replay test).

Owner: M4 · Tracker: M4-06 · Spec: CONTEXT §14 S3, §8.2, §11 (simulator generate/replay).
Test method: ``simulator generate --events 10000 --shuffle --dup-rate 0.10``, compute the
expected final positions and play counts offline, ``simulator replay`` the file, then read
DynamoDB (``ctx.client("dynamodb")``). Pass if 0 positions and 0 play counts differ.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S3"
TITLE = "Bad-input correctness"
OWNER = "M4"
TARGET = "10k shuffled events with 10 % duplicates → 0 wrong positions, 0 double counts"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M4: write this check (M4-06, see the docstring)")

"""S5 · Hot vs cold agreement.

Owner: M5 · Tracker: M5-06 · Spec: CONTEXT §14 S5, ``athena/reconcile_trending.sql``.
Test method: after the S4 run, compare today's DynamoDB trending counters (``TREND#<date>``
items) with distinct ``play`` events per episode in Athena. Pass if the totals, and each
episode, differ by at most 1 %.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S5"
TITLE = "Hot vs cold agreement"
OWNER = "M5"
TARGET = "DynamoDB trending vs Athena distinct plays within 1 %"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M5: write this check (M5-06, see the docstring)")

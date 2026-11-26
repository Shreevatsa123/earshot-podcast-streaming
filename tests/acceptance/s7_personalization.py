"""S7 · Personalization coverage.

Owner: M5 · Tracker: M5-07 · Spec: CONTEXT §14 S7, §7.4 (home rules).
Test method: run the recs state machine, then call ``GET /home`` as 100 sim users with at
least 3 plays and 20 with none (``ctx.api.get("/home", sim_user=...)``). Pass if every
eligible user gets a ``personalized`` row, every new user gets ``popular_fallback``, and no
response has zero rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S7"
TITLE = "Personalization coverage"
OWNER = "M5"
TARGET = "100 % of sampled users with ≥ 3 plays get a personalized row; new users get the fallback; never empty"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M5: write this check (M5-07, see the docstring)")

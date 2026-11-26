"""S1 · End-to-end user flow.

Owner: M1 · Spec: CONTEXT §14 S1, BRD FR-01–FR-03, FR-07.
Test method: scripted walkthrough with 5 test accounts (sign up, log in, browse, play,
pause, resume), pass/fail per step. The browser part is manual: automate what the API
covers (browse, progress) and record the browser walkthrough by hand in docs/results.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S1"
TITLE = "End-to-end user flow"
OWNER = "M1"
TARGET = "New user: sign up → log in → browse → play → pause → resume"


def run(ctx: Context) -> Measurement:
    raise NotImplementedError("M1: write this check (see the docstring)")

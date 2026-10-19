"""Recs writer Lambda: Athena result CSVs -> RECS + POPULAR items (CONTEXT §8.1, §10).

Owner: M5 · Tracker: M5-04 · Function: ``earshot-<stage>-recs-writer`` · Handler: ``recs_writer.handler.main``
Env (CONTEXT §9): STAGE, TABLE_NAME, LAKE_BUCKET.

STATUS: STUB. Not deployed until M5's recs construct creates the function.
"""

from __future__ import annotations

from typing import Any


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Must return ``{"run_id", "users_written", "popular_count"}`` (CONTEXT §10)."""
    raise NotImplementedError("M5-04: implement the recs writer per CONTEXT §10")

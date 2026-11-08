"""Ingest Lambda: ``POST /events`` -> the SNS events topic (CONTEXT §7.5, §10 "Message format").

Owner: M3 · Tracker: M3-02 · Function: ``earshot-<stage>-ingest`` · Handler: ``ingest.handler.main``
Env (CONTEXT §9): STAGE, TOPIC_ARN, ALLOWED_GENRES.

STATUS: STUB. Not deployed until M3's ingest construct creates the function.
"""

from __future__ import annotations

from typing import Any


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    raise NotImplementedError("M3-02: implement ingest per CONTEXT §7.5")

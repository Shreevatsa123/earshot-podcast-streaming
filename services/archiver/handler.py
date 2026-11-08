"""Archiver Lambda: SQS batch from the cold queue -> gzipped JSON Lines in the S3 lake (CONTEXT §9, §10).

Replaces Amazon Data Firehose. Each SQS record's ``body`` is ``{"events": [...]}``
(CONTEXT §10 "Message format").

Owner: M5 · Tracker: M5-02 · Function: ``earshot-<stage>-archiver`` · Handler: ``archiver.handler.main``
Env (CONTEXT §9): STAGE, LAKE_BUCKET.

STATUS: STUB. Not deployed until M5's archiver construct creates the function.
"""

from __future__ import annotations

from typing import Any


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Must return ``{"batchItemFailures": [...]}`` (CONTEXT §10)."""
    raise NotImplementedError("M5-02: implement the archiver per CONTEXT §10")

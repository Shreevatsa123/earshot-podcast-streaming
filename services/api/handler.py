"""API Lambda: all read routes (CONTEXT §7.3, §7.4).

Owner: M2 · Tracker: M2-05, M2-06 · Function: ``earshot-<stage>-api`` · Handler: ``api.handler.main``
Env (CONTEXT §9): STAGE, TABLE_NAME, FLAGS_PARAM, ALLOWED_GENRES.

STATUS: STUB. Not deployed until M2's API construct creates the function.
"""

from __future__ import annotations

from typing import Any


def main(event: dict[str, Any], context: Any) -> dict[str, Any]:
    raise NotImplementedError("M2-05: implement the routes in CONTEXT §7.3")

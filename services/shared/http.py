"""Helpers for API Lambdas behind the API Gateway HTTP API (payload format 2.0).

Spec: CONTEXT §7.1 (responses, errors, identity) and §7.2 (simulator group).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

#: Error codes and their HTTP status codes (CONTEXT §7.1).
ERROR_STATUS: dict[str, int] = {
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "INTERNAL": 500,
    "PIPELINE_OFFLINE": 503,
}

SIMULATOR_GROUP = "simulator"


def _json_default(value: Any) -> Any:
    """Make DynamoDB values JSON-serializable (Decimal -> int/float, set -> sorted list)."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_response(
    status: int, body: Any, headers: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Build a Lambda proxy response with a compact JSON body."""
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", **dict(headers or {})},
        "body": json.dumps(body, separators=(",", ":"), default=_json_default),
    }


def error_response(code: str, message: str) -> dict[str, Any]:
    """Build the standard error ``{"error": {"code", "message"}}`` (CONTEXT §7.1)."""
    if code not in ERROR_STATUS:
        raise ValueError(f"Unknown error code {code!r}; use one of {sorted(ERROR_STATUS)}")
    return json_response(ERROR_STATUS[code], {"error": {"code": code, "message": message}})


def parse_json_body(event: Mapping[str, Any]) -> Any:
    """Return the decoded JSON request body. Raises ``ValueError`` if it's missing or invalid."""
    raw = event.get("body")
    if raw is None:
        raise ValueError("Request body is empty")
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)


def jwt_claims(event: Mapping[str, Any]) -> dict[str, Any]:
    """Claims verified by the HTTP API JWT authorizer, or ``{}`` on unauthenticated routes."""
    context = event.get("requestContext") or {}
    authorizer = context.get("authorizer") or {}
    jwt = authorizer.get("jwt") or {}
    return dict(jwt.get("claims") or {})


def token_groups(claims: Mapping[str, Any]) -> set[str]:
    """Cognito groups from the ``cognito:groups`` claim.

    HTTP APIs pass array claims as a string such as ``"[simulator]"`` or
    ``"[listeners simulator]"``, so lists and strings are both handled (CONTEXT §7.2).
    """
    raw = claims.get("cognito:groups")
    if raw is None:
        return set()
    if isinstance(raw, (list, tuple, set, frozenset)):
        return {str(group) for group in raw}
    text = str(raw).strip().strip("[]")
    parts = (part.strip("\"'") for part in text.replace(",", " ").split())
    return {part for part in parts if part}


def is_simulator(claims: Mapping[str, Any]) -> bool:
    """True if the caller is in the ``simulator`` group (CONTEXT §7.2)."""
    return SIMULATOR_GROUP in token_groups(claims)

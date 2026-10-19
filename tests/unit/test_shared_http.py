import base64
import json
from decimal import Decimal

import pytest

from shared import http


def test_json_response_handles_dynamodb_decimals():
    response = http.json_response(200, {"plays": Decimal("3"), "score": Decimal("0.5")})
    assert response["statusCode"] == 200
    assert response["headers"]["content-type"] == "application/json"
    assert json.loads(response["body"]) == {"plays": 3, "score": 0.5}


@pytest.mark.parametrize(
    ("code", "status"),
    [("BAD_REQUEST", 400), ("UNAUTHORIZED", 401), ("FORBIDDEN", 403), ("NOT_FOUND", 404),
     ("INTERNAL", 500), ("PIPELINE_OFFLINE", 503)],
)
def test_error_response_format(code, status):
    response = http.error_response(code, "something went wrong")
    assert response["statusCode"] == status
    assert json.loads(response["body"]) == {"error": {"code": code, "message": "something went wrong"}}


def test_error_response_rejects_unknown_codes():
    with pytest.raises(ValueError):
        http.error_response("TEAPOT", "no")


def test_parse_json_body_plain_and_base64():
    payload = {"events": []}
    assert http.parse_json_body({"body": json.dumps(payload)}) == payload
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    assert http.parse_json_body({"body": encoded, "isBase64Encoded": True}) == payload
    with pytest.raises(ValueError):
        http.parse_json_body({})
    with pytest.raises(ValueError):
        http.parse_json_body({"body": "not json"})


def test_jwt_claims():
    event = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "abc"}}}}}
    assert http.jwt_claims(event) == {"sub": "abc"}
    assert http.jwt_claims({}) == {}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, False),
        ("[simulator]", True),
        ("[listeners simulator]", True),
        ("[listeners]", False),
        (["simulator"], True),
        ("simulator", True),
        ("[simulators]", False),
    ],
)
def test_is_simulator_parses_group_claim_defensively(raw, expected):
    claims = {} if raw is None else {"cognito:groups": raw}
    assert http.is_simulator(claims) is expected

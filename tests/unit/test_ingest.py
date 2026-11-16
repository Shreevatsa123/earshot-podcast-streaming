"""M3-02: ingest Lambda (CONTEXT §7.2, §7.5, §10 message format). No AWS: SNS is faked."""

import base64
import json

import pytest

from ingest import handler
from shared import clock

NOW = 1_794_000_000_000
TOPIC = "arn:aws:sns:us-east-1:123456789012:earshot-test-events"


class FakeSns:
    def __init__(self, failures=()):
        self.failures = list(failures)
        self.messages = []

    def publish(self, TopicArn, Message):  # noqa: N803 - boto3 argument names
        if self.failures:
            raise self.failures.pop(0)
        self.messages.append((TopicArn, json.loads(Message)))
        return {"MessageId": "1"}


class AwsError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


@pytest.fixture
def sns(monkeypatch):
    fake = FakeSns()
    monkeypatch.setattr(handler, "_sns_client", fake)
    monkeypatch.setattr(handler.time, "sleep", lambda s: None)
    monkeypatch.setattr(clock, "now_ms", lambda: NOW)
    monkeypatch.setenv("TOPIC_ARN", TOPIC)
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setenv("ALLOWED_GENRES", "true-crime,comedy,news,technology,business,science,sports,history")
    return fake


def ev(i=0, **overrides):
    base = {
        "event_id": f"8f0c1f9e-6c43-4b5e-9a37-0a6f8a1c2d{i:02d}",
        "session_id": "b1d2c3d4-e5f6-4789-a012-3456789abcde",
        "show_id": "920666",
        "episode_id": "16795090",
        "genre": "true-crime",
        "event_type": "heartbeat",
        "position_sec": 10 * i,
        "duration_sec": 2810,
        "client_ts": NOW - 1000,
        "region": "us-east",
        "device": "web",
    }
    base.update(overrides)
    return base


def request(body, *, groups=None, sub="user-123", raw=False, b64=False):
    claims = {"sub": sub} if sub else {}
    if groups is not None:
        claims["cognito:groups"] = groups
    text = body if raw else json.dumps(body)
    if b64:
        text = base64.b64encode(text.encode()).decode()
    return {
        "body": text,
        "isBase64Encoded": b64,
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
    }


def call(evt):
    response = handler.main(evt, None)
    return response["statusCode"], json.loads(response["body"])


def test_accepts_and_publishes_one_message(sns):
    status, body = call(request({"events": [ev(0), ev(1, user_id="sim-000001", server_ts=5)]}))
    assert status == 202
    assert body == {"accepted": 2, "rejected": []}
    assert len(sns.messages) == 1
    topic, message = sns.messages[0]
    assert topic == TOPIC
    events = message["events"]
    assert [e["user_id"] for e in events] == ["user-123", "user-123"]  # body user_id ignored
    assert all(e["server_ts"] == NOW and e["schema_version"] == 1 for e in events)


def test_partial_rejection_reports_index(sns):
    status, body = call(request({"events": [ev(0), ev(1, position_sec=-5), ev(2, region="moon")]}))
    assert status == 202
    assert body["accepted"] == 1
    assert body["rejected"] == [
        {"index": 1, "reason": "INVALID_FIELD:position_sec"},
        {"index": 2, "reason": "INVALID_FIELD:region"},
    ]
    assert len(sns.messages[0][1]["events"]) == 1


def test_nothing_valid_means_no_publish(sns):
    status, body = call(request({"events": ["nope"]}))
    assert (status, body["accepted"]) == (202, 0)
    assert body["rejected"] == [{"index": 0, "reason": "INVALID_JSON"}]
    assert sns.messages == []


@pytest.mark.parametrize("groups", ["[simulator]", ["simulator"], "[listeners simulator]"])
def test_simulator_keeps_sim_user_ids(sns, groups):
    status, body = call(
        request({"events": [ev(0, user_id="sim-000042"), ev(1, user_id="alice"), ev(2)]}, groups=groups)
    )
    assert status == 202
    assert body["accepted"] == 1
    assert body["rejected"] == [{"index": 1, "reason": "FORBIDDEN_USER"}, {"index": 2, "reason": "FORBIDDEN_USER"}]
    assert sns.messages[0][1]["events"][0]["user_id"] == "sim-000042"


def test_non_simulator_group_cannot_impersonate(sns):
    call(request({"events": [ev(0, user_id="sim-000042")]}, groups="[listeners]"))
    assert sns.messages[0][1]["events"][0]["user_id"] == "user-123"


@pytest.mark.parametrize(
    "body",
    ["not json", json.dumps([1]), json.dumps({"events": []}), json.dumps({"events": "x"}), json.dumps({})],
)
def test_bad_bodies_are_400(sns, body):
    status, resp = call(request(body, raw=True))
    assert status == 400
    assert resp["error"]["code"] == "BAD_REQUEST"


def test_more_than_25_events_is_400(sns):
    status, _ = call(request({"events": [ev(i) for i in range(26)]}))
    assert status == 400


def test_body_over_64kb_is_400(sns):
    status, _ = call(request({"events": [ev(0)], "pad": "x" * 70_000}))
    assert status == 400


def test_base64_body(sns):
    status, body = call(request({"events": [ev(0)]}, b64=True))
    assert (status, body["accepted"]) == (202, 1)


def test_missing_sub_is_401(sns):
    status, _ = call(request({"events": [ev(0)]}, sub=None))
    assert status == 401


def test_throttling_is_retried(sns):
    sns.failures = [AwsError("Throttling"), AwsError("Throttling")]
    status, body = call(request({"events": [ev(0)]}))
    assert body == {"accepted": 1, "rejected": []}
    assert len(sns.messages) == 1


def test_persistent_throttling_rejects_all_as_throttled(sns):
    sns.failures = [AwsError("Throttling")] * 4
    status, body = call(request({"events": [ev(0), ev(1, genre="x"), ev(2)]}))
    assert status == 202
    assert body["accepted"] == 0
    assert body["rejected"] == [
        {"index": 0, "reason": "THROTTLED"},
        {"index": 1, "reason": "INVALID_FIELD:genre"},
        {"index": 2, "reason": "THROTTLED"},
    ]


def test_non_retryable_error_is_not_retried(sns):
    sns.failures = [AwsError("AuthorizationError"), AwsError("Throttling")]
    _, body = call(request({"events": [ev(0)]}))
    assert body["rejected"] == [{"index": 0, "reason": "THROTTLED"}]
    assert len(sns.failures) == 1  # only one attempt was made


def test_metrics_are_emitted(sns, capsys):
    call(request({"events": [ev(0), ev(1, device="tv")]}))
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    metrics = [line for line in lines if "_aws" in line]
    assert metrics and metrics[-1]["EventsAccepted"] == 1 and metrics[-1]["EventsRejected"] == 1

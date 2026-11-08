import json

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from processor import handler


@pytest.fixture
def progress_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="earshot-test-main",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def playback_event(
    *,
    client_ts: int,
    position_sec: int,
    event_type: str = "pause",
    duration_sec: int = 100,
) -> dict[str, object]:
    return {
        "event_id": "8f0c1f9e-6c43-4b5e-9a37-0a6f8a1c2d11",
        "schema_version": 1,
        "user_id": "sim-000042",
        "session_id": "b1d2c3d4-e5f6-4789-a012-3456789abcde",
        "show_id": "920666",
        "episode_id": "16795090",
        "genre": "true-crime",
        "event_type": event_type,
        "position_sec": position_sec,
        "duration_sec": duration_sec,
        "client_ts": client_ts,
        "server_ts": client_ts + 20,
        "region": "us-east",
        "device": "web",
    }


def sqs_record(events: list[object], message_id: str) -> dict[str, str]:
    return {"messageId": message_id, "body": json.dumps({"events": events})}


def test_main_keeps_newest_progress_when_events_arrive_out_of_order(
    progress_table, monkeypatch, capsys
):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    newer = playback_event(client_ts=1_793_548_801_200, position_sec=80)
    older = playback_event(client_ts=1_793_548_801_100, position_sec=40)

    result = handler.main(
        {"Records": [sqs_record([newer], "newer"), sqs_record([older], "older")]},
        context=None,
    )

    item = progress_table.get_item(
        Key={"PK": "USER#sim-000042", "SK": "PROG#16795090"}
    )["Item"]
    assert result == {"batchItemFailures": []}
    assert item["client_ts"] == newer["client_ts"]
    assert item["position_sec"] == 80
    assert item["updated_at"] > 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["StaleEvents"] == 1


@pytest.mark.parametrize(
    ("event_type", "position_sec", "expected_completed"),
    [
        ("complete", 20, True),
        ("heartbeat", 95, True),
        ("heartbeat", 94, False),
    ],
)
def test_update_progress_sets_completion_status(
    progress_table, event_type, position_sec, expected_completed
):
    event = playback_event(
        client_ts=1_793_548_801_200,
        position_sec=position_sec,
        event_type=event_type,
    )

    assert handler.update_progress(progress_table, event, updated_at_ms=1_793_548_801_312)
    item = progress_table.get_item(
        Key={"PK": "USER#sim-000042", "SK": "PROG#16795090"}
    )["Item"]
    assert item["completed"] is expected_completed
    assert item["updated_at"] == 1_793_548_801_312


@pytest.mark.parametrize(
    "body",
    ["not JSON", json.dumps({"payload": []}), json.dumps({"events": {}})],
)
def test_decode_sqs_message_requires_an_events_array(body):
    with pytest.raises(ValueError, match="SQS message body"):
        handler.decode_sqs_message({"body": body})


def test_main_skips_malformed_messages_and_events(progress_table, monkeypatch, capsys):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    valid = playback_event(client_ts=1_793_548_801_200, position_sec=80)

    result = handler.main(
        {
            "Records": [
                {"messageId": "malformed", "body": "not JSON"},
                sqs_record([[], valid], "mixed"),
            ]
        },
        context=None,
    )

    item = progress_table.get_item(
        Key={"PK": "USER#sim-000042", "SK": "PROG#16795090"}
    )["Item"]
    assert result == {"batchItemFailures": []}
    assert item["position_sec"] == 80
    batch_log = json.loads(capsys.readouterr().out.splitlines()[0])
    assert batch_log["malformed_messages"] == 1
    assert batch_log["malformed_events"] == 1


def test_main_reports_transient_failure_by_sqs_message_id(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    event = playback_event(client_ts=1_793_548_801_200, position_sec=80)
    error = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Retry the request",
            }
        },
        "UpdateItem",
    )

    class FailingTable:
        def update_item(self, **kwargs):
            raise error

    class FakeDynamoDB:
        def Table(self, name):
            return FailingTable()

    monkeypatch.setattr(handler.boto3, "resource", lambda service: FakeDynamoDB())

    result = handler.main({"Records": [sqs_record([event], "retry-this-message")]}, context=None)

    assert result == {"batchItemFailures": [{"itemIdentifier": "retry-this-message"}]}


def test_main_surfaces_non_retryable_aws_errors(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    event = playback_event(client_ts=1_793_548_801_200, position_sec=80)
    error = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "Invalid request"}},
        "UpdateItem",
    )

    class FailingTable:
        def update_item(self, **kwargs):
            raise error

    class FakeDynamoDB:
        def Table(self, name):
            return FailingTable()

    monkeypatch.setattr(handler.boto3, "resource", lambda service: FakeDynamoDB())

    with pytest.raises(ClientError, match="Invalid request"):
        handler.main({"Records": [sqs_record([event], "invalid-request")]}, context=None)

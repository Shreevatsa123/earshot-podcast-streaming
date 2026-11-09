import json
from types import SimpleNamespace

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


def buffer_event(
    *,
    event_id: str,
    server_ts: int = 1_793_548_801_200,
    region: str = "us-east",
) -> dict[str, object]:
    event = playback_event(
        client_ts=server_ts,
        position_sec=40,
        event_type="buffer",
    )
    event.update(event_id=event_id, server_ts=server_ts, region=region)
    return event


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


def test_main_counts_distinct_play_events_once(progress_table, monkeypatch, capsys):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    now_ms = 1_798_000_000_000
    monkeypatch.setattr(handler.clock, "now_ms", lambda: now_ms)
    play = playback_event(
        client_ts=1_793_548_801_200,
        position_sec=0,
        event_type="play",
    )

    result = handler.main(
        {"Records": [sqs_record([play], "first"), sqs_record([play], "duplicate")]},
        context=None,
    )

    trend_key = {
        "PK": f"TREND#{handler.clock.utc_date(play['server_ts'])}",
        "SK": f"EP#{play['episode_id']}",
    }
    trend = progress_table.get_item(Key=trend_key)["Item"]
    assert result == {"batchItemFailures": []}
    assert trend["plays"] == 1
    assert trend["show_id"] == play["show_id"]
    assert trend["ttl"] == now_ms // 1000 + 8 * 24 * 60 * 60
    marker = progress_table.get_item(
        Key={"PK": f"EVT#{play['event_id']}", "SK": "EVT"}
    )["Item"]
    assert marker["ttl"] == now_ms // 1000 + 24 * 60 * 60
    metrics = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert metrics["PlaysCounted"] == 1
    assert metrics["DuplicateEvents"] == 1
    assert metrics["StaleEvents"] == 1


def test_main_skips_play_without_trending_identity_fields(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    malformed_play = playback_event(
        client_ts=1_793_548_801_200,
        position_sec=0,
        event_type="play",
    )
    del malformed_play["event_id"]

    class FakeTable:
        def update_item(self, **kwargs):
            pytest.fail("malformed play must not update progress")

    class FakeDynamoDB:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr(handler.boto3, "resource", lambda service: FakeDynamoDB())

    result = handler.main(
        {"Records": [sqs_record([malformed_play], "missing-event-id")]},
        context=None,
    )

    assert result == {"batchItemFailures": []}


def test_main_retries_a_transient_trending_transaction_conflict(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    event = playback_event(
        client_ts=1_793_548_801_200,
        position_sec=0,
        event_type="play",
    )
    error = ClientError(
        {
            "Error": {"Code": "TransactionCanceledException", "Message": "Transaction conflict"},
            "CancellationReasons": [
                {"Code": "None"},
                {"Code": "TransactionConflict"},
            ],
        },
        "TransactWriteItems",
    )

    class FakeTable:
        name = "earshot-test-main"

        def __init__(self):
            self.meta = SimpleNamespace(client=self)

        def update_item(self, **kwargs):
            return None

        def transact_write_items(self, **kwargs):
            raise error

    class FakeDynamoDB:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr(handler.boto3, "resource", lambda service: FakeDynamoDB())

    result = handler.main({"Records": [sqs_record([event], "transaction-conflict")]}, context=None)

    assert result == {"batchItemFailures": [{"itemIdentifier": "transaction-conflict"}]}


def test_main_publishes_one_qoe_alert_when_region_minute_reaches_threshold(
    progress_table, monkeypatch, capsys
):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("QOE_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:earshot-test-qoe-alerts")
    monkeypatch.setenv("QOE_THRESHOLD", "2")
    now_ms = 1_798_000_000_000
    monkeypatch.setattr(handler.clock, "now_ms", lambda: now_ms)
    published = []

    class FakeSNS:
        def publish(self, **kwargs):
            published.append(kwargs)
            return {"MessageId": "alert-message"}

    monkeypatch.setattr(handler.boto3, "client", lambda service: FakeSNS())
    first = buffer_event(event_id="buffer-1")
    second = buffer_event(event_id="buffer-2", server_ts=first["server_ts"] + 1)

    result = handler.main(
        {"Records": [sqs_record([first, second], "buffers")]},
        context=None,
    )

    window = progress_table.get_item(
        Key={
            "PK": "QOE#us-east",
            "SK": f"MIN#{handler.clock.utc_minute(first['server_ts'])}",
        }
    )["Item"]
    assert result == {"batchItemFailures": []}
    assert window["buffers"] == 2
    assert window["ttl"] == now_ms // 1000 + 24 * 60 * 60
    assert len(published) == 1
    assert published[0]["TopicArn"].endswith(":earshot-test-qoe-alerts")
    assert json.loads(published[0]["Message"]) == {
        "region": "us-east",
        "minute": handler.clock.utc_minute(first["server_ts"]),
        "buffers": 2,
        "threshold": 2,
    }
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["QoEAlertsSent"] == 1


def test_main_deduplicates_buffer_events_before_counting_or_alerting(
    progress_table, monkeypatch, capsys
):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("QOE_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:earshot-test-qoe-alerts")
    monkeypatch.setenv("QOE_THRESHOLD", "1")
    published = []

    class FakeSNS:
        def publish(self, **kwargs):
            published.append(kwargs)
            return {"MessageId": "alert-message"}

    monkeypatch.setattr(handler.boto3, "client", lambda service: FakeSNS())
    buffer = buffer_event(event_id="replayed-buffer")

    result = handler.main(
        {
            "Records": [
                sqs_record([buffer], "first-delivery"),
                sqs_record([buffer], "duplicate-delivery"),
            ]
        },
        context=None,
    )

    window = progress_table.get_item(
        Key={
            "PK": "QOE#us-east",
            "SK": f"MIN#{handler.clock.utc_minute(buffer['server_ts'])}",
        }
    )["Item"]
    metrics = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result == {"batchItemFailures": []}
    assert window["buffers"] == 1
    assert len(published) == 1
    assert metrics["DuplicateEvents"] == 1
    assert metrics["QoEAlertsSent"] == 1


def test_qoe_windows_are_separate_by_region_and_server_minute(progress_table, monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    base = 1_793_548_801_200
    east = buffer_event(event_id="east-buffer", server_ts=base, region="us-east")
    west = buffer_event(event_id="west-buffer", server_ts=base, region="us-west")
    next_minute = buffer_event(
        event_id="next-minute-buffer",
        server_ts=base + 60_000,
        region="us-east",
    )

    result = handler.main(
        {"Records": [sqs_record([east, west, next_minute], "three-windows")]},
        context=None,
    )

    assert result == {"batchItemFailures": []}
    for buffer in (east, west, next_minute):
        window = progress_table.get_item(
            Key={
                "PK": f"QOE#{buffer['region']}",
                "SK": f"MIN#{handler.clock.utc_minute(buffer['server_ts'])}",
            }
        )["Item"]
        assert window["buffers"] == 1


@pytest.mark.parametrize(
    "invalid_field",
    ["event_id", "server_ts", "region"],
)
def test_main_skips_buffer_events_missing_qoe_fields(monkeypatch, invalid_field):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    malformed = buffer_event(event_id="invalid-buffer")
    malformed.pop(invalid_field)

    class FakeTable:
        def update_item(self, **kwargs):
            pytest.fail("malformed QoE buffer must not update progress")

    class FakeDynamoDB:
        def Table(self, name):
            return FakeTable()

    monkeypatch.setattr(handler.boto3, "resource", lambda service: FakeDynamoDB())

    result = handler.main({"Records": [sqs_record([malformed], "invalid-buffer")]}, context=None)

    assert result == {"batchItemFailures": []}


def test_qoe_threshold_defaults_to_thirty_and_rejects_invalid_values(monkeypatch):
    monkeypatch.delenv("QOE_THRESHOLD", raising=False)
    assert handler.qoe_threshold() == 30

    monkeypatch.setenv("QOE_THRESHOLD", "not-a-number")
    with pytest.raises(ValueError, match="positive integer"):
        handler.qoe_threshold()

    monkeypatch.setenv("QOE_THRESHOLD", "0")
    with pytest.raises(ValueError, match="positive integer"):
        handler.qoe_threshold()

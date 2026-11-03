import base64
import json

import boto3
import pytest
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


def kinesis_record(event: dict[str, object], sequence_number: str) -> dict[str, object]:
    encoded = base64.b64encode(json.dumps(event).encode("utf-8")).decode("ascii")
    return {
        "kinesis": {"data": encoded, "sequenceNumber": sequence_number},
        "eventSource": "aws:kinesis",
        "eventID": f"shardId-000000000000:{sequence_number}",
    }


def test_main_keeps_newest_progress_when_events_arrive_out_of_order(
    progress_table, monkeypatch, capsys
):
    monkeypatch.setenv("TABLE_NAME", "earshot-test-main")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    newer = playback_event(client_ts=1_793_548_801_200, position_sec=80)
    older = playback_event(client_ts=1_793_548_801_100, position_sec=40)

    result = handler.main(
        {"Records": [kinesis_record(newer, "2"), kinesis_record(older, "1")]},
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


def test_decode_kinesis_record_requires_json_object():
    encoded = base64.b64encode(b"[]").decode("ascii")

    with pytest.raises(ValueError, match="JSON object"):
        handler.decode_kinesis_record({"kinesis": {"data": encoded}})

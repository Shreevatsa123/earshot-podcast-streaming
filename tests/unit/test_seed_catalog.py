"""Tests for scripts/catalog/seed_catalog.py (M2-03): the real catalog into a moto DynamoDB table."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "catalog"))
import seed_catalog  # noqa: E402
from fetch_catalog import DEFAULT_OUT  # noqa: E402

CATALOG = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
SHOW_ATTRS = {"show_id", "title", "author", "description", "image_url", "genre", "episode_count"}
EPISODE_ATTRS = {"show_id", "episode_id", "title", "audio_url", "duration_sec", "published_at", "image_url", "genre"}


@pytest.fixture
def table(monkeypatch):
    """An empty table shaped like core.py's: PK/SK strings plus GSI1."""
    for key, value in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        string_keys = ("PK", "SK", "GSI1PK", "GSI1SK")
        yield boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="earshot-test-main",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in string_keys],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )


def item_count(table) -> int:
    count, kwargs = 0, {"Select": "COUNT"}
    while True:
        page = table.scan(**kwargs)
        count += page["Count"]
        if "LastEvaluatedKey" not in page:
            return count
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def test_seed_writes_every_item_and_rerun_overwrites(table):
    expected = len(CATALOG["shows"]) + len(CATALOG["episodes"]) + 1
    assert seed_catalog.seed(table, CATALOG) == expected
    seed_catalog.seed(table, CATALOG)
    assert item_count(table) == expected


def test_items_have_exactly_the_contract_attributes(table):
    seed_catalog.seed(table, CATALOG)
    show, episode = CATALOG["shows"][0], CATALOG["episodes"][0]

    show_item = table.get_item(Key={"PK": f"SHOW#{show['show_id']}", "SK": "META"})["Item"]
    assert set(show_item) == SHOW_ATTRS | {"PK", "SK", "GSI1PK", "GSI1SK"}
    assert show_item["GSI1PK"] == f"GENRE#{show['genre']}"

    key = {"PK": f"SHOW#{episode['show_id']}", "SK": f"EP#{episode['episode_id']}"}
    episode_item = table.get_item(Key=key)["Item"]
    assert set(episode_item) == EPISODE_ATTRS | {"PK", "SK"}
    assert int(episode_item["duration_sec"]) == episode["duration_sec"]

    featured = table.get_item(Key={"PK": "FEATURED", "SK": "GLOBAL"})["Item"]
    assert featured["items"] == CATALOG["featured"]


def test_main_reports_a_missing_table(table, capsys):
    assert seed_catalog.main(["--stage", "nosuch"]) == 1  # earshot-nosuch-main doesn't exist
    assert "doesn't exist" in capsys.readouterr().err


def test_genre_index_lists_shows_like_the_shows_sample(table):
    """GET /shows?genre=true-crime reads GSI1; its order must match shows.json (M2-07)."""
    seed_catalog.seed(table, CATALOG)
    found = table.query(
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :genre",
        ExpressionAttributeValues={":genre": "GENRE#true-crime"},
    )["Items"]
    sample = json.loads((REPO / "contracts" / "samples" / "shows.json").read_text(encoding="utf-8"))
    assert [item["show_id"] for item in found] == [show["show_id"] for show in sample["shows"]]

"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def ddb_table(monkeypatch):
    """An empty moto DynamoDB table shaped like ``earshot-<stage>-main`` (core.py):
    PK/SK strings plus GSI1. Named ``earshot-test-main``."""
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    for key, value in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with moto.mock_aws():
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

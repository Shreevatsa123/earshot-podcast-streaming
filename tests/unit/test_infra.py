"""Synthesis tests for the CDK app. Skipped when aws-cdk-lib isn't installed (run ``make install``)."""

import json

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Match, Template  # noqa: E402

from earshot_infra import common  # noqa: E402
from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402
from earshot_infra.stacks.pipeline_stack import PipelineStack  # noqa: E402

ACCOUNT = "123456789012"


def synth(stage: str, alert_email: str | None = None) -> tuple[Template, Template]:
    app = cdk.App()
    cfg = StageConfig(stage=stage, account=ACCOUNT, alert_email=alert_email)
    env = cdk.Environment(account=cfg.account, region=cfg.region)
    base = BaseStack(app, cfg.stack_name("base"), cfg=cfg, env=env)
    pipeline = PipelineStack(app, cfg.stack_name("pipeline"), cfg=cfg, env=env)
    return Template.from_stack(base), Template.from_stack(pipeline)


def test_table_matches_contract():
    base, _ = synth("dev")
    base.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "earshot-dev-main",
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            "GlobalSecondaryIndexes": [
                Match.object_like(
                    {
                        "IndexName": "GSI1",
                        "KeySchema": [
                            {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                            {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                )
            ],
            "TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True},
        },
    )


def test_shared_resources_use_contract_names():
    base, _ = synth("dev")
    base.has_resource_properties("AWS::S3::Bucket", {"BucketName": f"earshot-dev-lake-{ACCOUNT}"})
    base.has_resource_properties("AWS::SNS::Topic", {"TopicName": "earshot-dev-qoe-alerts"})
    base.has_resource_properties("AWS::SNS::Topic", {"TopicName": "earshot-dev-ops-alerts"})
    base.has_resource_properties(
        "AWS::SSM::Parameter",
        {
            "Name": "/earshot/dev/flags",
            "Type": "String",
            "Tier": "Standard",
            "Value": '{"recs_enabled":true,"recs_fault_injection":false}',
        },
    )


def test_dev_data_is_destroyed_and_prod_data_is_retained():
    dev, _ = synth("dev")
    prod, _ = synth("prod")
    dev.has_resource("AWS::DynamoDB::Table", {"DeletionPolicy": "Delete"})
    dev.has_resource("AWS::S3::Bucket", {"DeletionPolicy": "Delete"})
    prod.has_resource("AWS::DynamoDB::Table", {"DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain"})

    # The prod lake bucket is retained and never auto-emptied (other buckets may be).
    lake = prod.find_resources(
        "AWS::S3::Bucket", {"Properties": {"BucketName": f"earshot-prod-lake-{ACCOUNT}"}}
    )
    assert len(lake) == 1
    (lake_id, lake_bucket), = lake.items()
    assert lake_bucket["DeletionPolicy"] == "Retain"
    auto_deletes = prod.find_resources("Custom::S3AutoDeleteObjects")
    assert not any(lake_id in json.dumps(resource) for resource in auto_deletes.values())


def test_stacks_are_decoupled():
    """CONTEXT §5: no CloudFormation exports/imports between base and pipeline."""
    base, pipeline = synth("dev")
    for name, output in base.to_json().get("Outputs", {}).items():
        assert "Export" not in output, f"Output {name} is exported; reference resources by name instead"
    assert "Fn::ImportValue" not in json.dumps(pipeline.to_json())


def test_alert_email_subscribes_to_both_topics():
    base, _ = synth("dev", alert_email="m6@example.com")
    base.resource_count_is("AWS::SNS::Subscription", 2)
    base.has_resource_properties(
        "AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": "m6@example.com"}
    )


def test_resources_are_tagged():
    base, _ = synth("dev")
    base.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "Tags": Match.array_with([{"Key": "owner", "Value": "M6"}]),
        },
    )
    base.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "Tags": Match.array_with([{"Key": "project", "Value": "earshot"}]),
        },
    )
    base.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "Tags": Match.array_with([{"Key": "stage", "Value": "dev"}]),
        },
    )


def test_python_function_helper_defaults():
    app = cdk.App()
    cfg = StageConfig(stage="dev", account=ACCOUNT)
    stack = cdk.Stack(app, "HelperTest", env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    common.python_function(
        stack,
        "Function",
        cfg=cfg,
        name="api",
        handler="api.handler.main",
        environment={"TABLE_NAME": cfg.table_name},
    )
    template = Template.from_stack(stack)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "earshot-dev-api",
            "Handler": "api.handler.main",
            "Runtime": "python3.12",
            "Architectures": ["arm64"],
            "MemorySize": 256,
            "Environment": {"Variables": {"STAGE": "dev", "TABLE_NAME": "earshot-dev-main"}},
        },
    )
    template.has_resource_properties(
        "AWS::Logs::LogGroup", {"LogGroupName": "/aws/lambda/earshot-dev-api", "RetentionInDays": 7}
    )

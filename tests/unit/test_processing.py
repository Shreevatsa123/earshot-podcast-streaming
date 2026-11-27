import json

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Match, Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs.core import Core  # noqa: E402
from earshot_infra.constructs.processing import ProcessingBase, ProcessingPipeline  # noqa: E402
from earshot_infra.constructs.topic import EventsTopic  # noqa: E402

ACCOUNT = "123456789012"


def base_template() -> tuple[Template, StageConfig]:
    app = cdk.App()
    cfg = StageConfig(stage="dev", account=ACCOUNT)
    stack = cdk.Stack(app, "Base", env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    core = Core(stack, "Core", cfg=cfg)
    topic = EventsTopic(stack, "EventsTopic", cfg=cfg)
    ProcessingBase(stack, "Processing", cfg=cfg, core=core, topic=topic.topic)
    return Template.from_stack(stack), cfg


def test_processing_base_creates_hot_queue_dlq_and_subscriber():
    template, cfg = base_template()
    resources = template.to_json()["Resources"]
    queues = {
        resource["Properties"]["QueueName"]: (logical_id, resource)
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::SQS::Queue"
    }

    queue_id, queue = queues[cfg.hot_queue]
    dlq_id, dlq = queues[cfg.processor_dlq]
    assert queue["Properties"]["MessageRetentionPeriod"] == 1_209_600
    assert queue["Properties"]["VisibilityTimeout"] == 300
    assert queue["Properties"]["SqsManagedSseEnabled"] is True
    assert queue["Properties"]["RedrivePolicy"] == {
        "deadLetterTargetArn": {"Fn::GetAtt": [dlq_id, "Arn"]},
        "maxReceiveCount": 5,
    }
    assert dlq["Properties"]["MessageRetentionPeriod"] == 1_209_600
    assert dlq["Properties"]["SqsManagedSseEnabled"] is True
    assert queue["DeletionPolicy"] == "Delete"
    assert dlq["DeletionPolicy"] == "Delete"
    assert queue_id

    template.has_resource_properties(
        "AWS::SNS::Subscription",
        {
            "Protocol": "sqs",
            "RawMessageDelivery": True,
            "Endpoint": {"Fn::GetAtt": [queue_id, "Arn"]},
        },
    )


def test_processing_base_configures_processor_and_permissions():
    template, cfg = base_template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": cfg.function_name("processor"),
            "Handler": "processor.handler.main",
            "Runtime": "python3.12",
            "Environment": {
                "Variables": {
                    "STAGE": "dev",
                    "TABLE_NAME": cfg.table_name,
                    "QOE_TOPIC_ARN": Match.any_value(),
                    "QOE_THRESHOLD": "30",
                }
            },
        },
    )
    policies = template.find_resources("AWS::IAM::Policy")
    serialized_policies = json.dumps(policies)
    for action in ("dynamodb:UpdateItem", "sns:Publish", "sqs:ReceiveMessage"):
        assert action in serialized_policies


def test_processing_pipeline_uses_contract_mapping_settings():
    app = cdk.App()
    cfg = StageConfig(stage="dev", account=ACCOUNT)
    stack = cdk.Stack(app, "Pipeline", env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    ProcessingPipeline(stack, "Processing", cfg=cfg)
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {
            "EventSourceArn": cfg.hot_queue_arn,
            "FunctionName": cfg.function_name("processor"),
            "BatchSize": 100,
            "MaximumBatchingWindowInSeconds": 1,
            "FunctionResponseTypes": ["ReportBatchItemFailures"],
            "ScalingConfig": {"MaximumConcurrency": 5},
        },
    )

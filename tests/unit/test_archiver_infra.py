"""M5-02: the archiver's CDK constructs (CONTEXT §5, §10).

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

import json

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs import archiver  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402
from earshot_infra.stacks.pipeline_stack import PipelineStack  # noqa: E402

ACCOUNT = "123456789012"
STAGE = "m5-dev"


@pytest.fixture(scope="module")
def stacks() -> tuple[BaseStack, Template, Template]:
    app = cdk.App()
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    env = cdk.Environment(account=ACCOUNT, region=cfg.region)
    # Both stacks exist before either template is read (CDK refuses changes after synth).
    base = BaseStack(app, cfg.stack_name("base"), cfg=cfg, env=env)
    pipeline = PipelineStack(app, cfg.stack_name("pipeline"), cfg=cfg, env=env)
    return base, Template.from_stack(base), Template.from_stack(pipeline)


def queue(template: Template, name: str) -> tuple[str, dict]:
    found = template.find_resources("AWS::SQS::Queue", {"Properties": {"QueueName": name}})
    assert len(found) == 1, f"expected one queue {name}"
    return next(iter(found.items()))


def test_cold_queue_settings(stacks):
    _, base, _ = stacks
    dlq_id, dlq = queue(base, f"earshot-{STAGE}-archiver-dlq")
    _, cold = queue(base, f"earshot-{STAGE}-cold")
    props = cold["Properties"]
    assert props["SqsManagedSseEnabled"] is True  # SNS can't deliver to KMS-managed queues
    assert props["MessageRetentionPeriod"] == 14 * 24 * 3600
    assert props["VisibilityTimeout"] == 900
    assert props["RedrivePolicy"] == {"deadLetterTargetArn": {"Fn::GetAtt": [dlq_id, "Arn"]}, "maxReceiveCount": 5}
    assert dlq["Properties"]["SqsManagedSseEnabled"] is True
    assert dlq["Properties"]["MessageRetentionPeriod"] == 14 * 24 * 3600
    assert cold["DeletionPolicy"] == dlq["DeletionPolicy"] == "Delete"


def test_visibility_timeout_covers_six_function_runs_plus_the_window():
    """CONTEXT §10: otherwise a slow batch reappears and is archived twice while still running."""
    minimum = 6 * archiver.FUNCTION_TIMEOUT_SECONDS + archiver.BATCHING_WINDOW.to_seconds()
    assert archiver.VISIBILITY_TIMEOUT.to_seconds() >= minimum


def test_cold_queue_subscribes_to_the_events_topic_with_raw_delivery(stacks):
    """Without raw delivery every body is an SNS envelope and the archiver rejects them all."""
    _, base, _ = stacks
    cold_id, _ = queue(base, f"earshot-{STAGE}-cold")
    topics = base.find_resources("AWS::SNS::Topic", {"Properties": {"TopicName": f"earshot-{STAGE}-events"}})
    (topic_id,) = topics
    subscriptions = [
        s["Properties"]
        for s in base.find_resources("AWS::SNS::Subscription").values()
        if s["Properties"]["Endpoint"] == {"Fn::GetAtt": [cold_id, "Arn"]}
    ]
    assert subscriptions == [
        {
            "Endpoint": {"Fn::GetAtt": [cold_id, "Arn"]},
            "Protocol": "sqs",
            "RawMessageDelivery": True,
            "TopicArn": {"Ref": topic_id},
        }
    ]
    # ...and the queue lets that topic, and only that topic, send to it.
    policies = [
        p["Properties"]["PolicyDocument"]["Statement"]
        for p in base.find_resources("AWS::SQS::QueuePolicy").values()
        if p["Properties"]["Queues"] == [{"Ref": cold_id}]
    ]
    assert policies == [
        [
            {
                "Action": "sqs:SendMessage",
                "Condition": {"ArnEquals": {"aws:SourceArn": {"Ref": topic_id}}},
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Resource": {"Fn::GetAtt": [cold_id, "Arn"]},
            }
        ]
    ]


def test_archiver_function(stacks):
    _, base, _ = stacks
    base.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": f"earshot-{STAGE}-archiver",
            "Handler": "archiver.handler.main",
            "Runtime": "python3.12",
            "Architectures": ["arm64"],
            "Timeout": 60,
            "Environment": {"Variables": {"STAGE": STAGE, "LAKE_BUCKET": f"earshot-{STAGE}-lake-{ACCOUNT}"}},
        },
    )


def test_archiver_may_only_write_events_and_consume_the_cold_queue(stacks):
    _, base, _ = stacks
    cold_id, _ = queue(base, f"earshot-{STAGE}-cold")
    (function_id,) = base.find_resources(
        "AWS::Lambda::Function", {"Properties": {"FunctionName": f"earshot-{STAGE}-archiver"}}
    )
    role = base.find_resources("AWS::Lambda::Function")[function_id]["Properties"]["Role"]["Fn::GetAtt"][0]
    statements = [
        statement
        for policy in base.find_resources("AWS::IAM::Policy").values()
        if {"Ref": role} in policy["Properties"]["Roles"]
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]
    resources = json.dumps([s["Resource"] for s in statements])
    s3 = [s for s in statements if any(a.startswith("s3:") for a in s["Action"])]
    assert len(s3) == 1 and "s3:PutObject" in s3[0]["Action"]
    assert not any(a.startswith(("s3:Get", "s3:Delete", "s3:List")) for a in s3[0]["Action"])
    assert s3[0]["Resource"]["Fn::Join"][1][1] == "/events/*"  # nothing outside events/
    sqs = [s for s in statements if any(a.startswith("sqs:") for a in s["Action"])]
    assert len(sqs) == 1 and {"sqs:ReceiveMessage", "sqs:DeleteMessage"} <= set(sqs[0]["Action"])
    assert sqs[0]["Resource"] == {"Fn::GetAtt": [cold_id, "Arn"]}
    assert "dynamodb" not in resources.lower()


def test_archiver_exposes_its_resources(stacks):
    base, _, _ = stacks
    construct = base.node.find_child("Archiver")
    assert isinstance(construct, archiver.ArchiverBase)
    assert construct.function is not None and construct.queue is not None and construct.dlq is not None


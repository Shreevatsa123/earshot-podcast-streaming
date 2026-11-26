"""Monitoring constructs (M6-05). Skipped when aws-cdk-lib isn't installed (run ``make install``)."""

import json

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk import aws_apigatewayv2 as apigwv2  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs import monitoring as monitoring_module  # noqa: E402
from earshot_infra.constructs.core import Core  # noqa: E402
from earshot_infra.constructs.monitoring import Monitoring, MonitoringPipeline  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402
from earshot_infra.stacks.pipeline_stack import PipelineStack  # noqa: E402
from shared import log  # noqa: E402

ACCOUNT = "123456789012"
BASE_ALARMS = {
    "earshot-prod-processor-dlq-not-empty",
    "earshot-prod-archiver-dlq-not-empty",
    "earshot-prod-api-5xx-rate",
    "earshot-prod-lambda-throttles",
    "earshot-prod-archiver-errors",
}


def build(stage: str, *, with_api: bool = True) -> tuple[Monitoring, Template]:
    app = cdk.App()
    cfg = StageConfig(stage=stage, account=ACCOUNT)
    stack = cdk.Stack(app, "MonitoringTest", env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    core = Core(stack, "Core", cfg=cfg)
    http_api = apigwv2.HttpApi(stack, "Api") if with_api else None
    monitoring = Monitoring(stack, "Monitoring", cfg=cfg, core=core, http_api=http_api)
    return monitoring, Template.from_stack(stack)


def build_pipeline(stage: str) -> Template:
    app = cdk.App()
    cfg = StageConfig(stage=stage, account=ACCOUNT)
    stack = cdk.Stack(app, "PipelineMonitoringTest", env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    MonitoringPipeline(stack, "Monitoring", cfg=cfg)
    return Template.from_stack(stack)


def alarm_names(template: Template) -> set[str]:
    return {a["Properties"]["AlarmName"] for a in template.find_resources("AWS::CloudWatch::Alarm").values()}


def test_every_stage_gets_a_dashboard():
    for stage in ("dev", "prod"):
        _, template = build(stage)
        template.resource_count_is("AWS::CloudWatch::Dashboard", 1)
        template.has_resource_properties("AWS::CloudWatch::Dashboard", {"DashboardName": f"earshot-{stage}"})


def test_prod_alarms_email_ops_and_ignore_missing_data():
    _, template = build("prod")
    assert alarm_names(template) == BASE_ALARMS
    (ops_topic_id,) = template.find_resources(
        "AWS::SNS::Topic", {"Properties": {"TopicName": "earshot-prod-ops-alerts"}}
    )
    for alarm in template.find_resources("AWS::CloudWatch::Alarm").values():
        props = alarm["Properties"]
        assert props["AlarmActions"] == [{"Ref": ops_topic_id}]
        assert props["TreatMissingData"] == "notBreaching"


def test_other_stages_have_no_alarms():
    _, base = build("dev")
    base.resource_count_is("AWS::CloudWatch::Alarm", 0)
    build_pipeline("dev").resource_count_is("AWS::CloudWatch::Alarm", 0)


def test_api_5xx_alarm_uses_the_rate():
    _, template = build("prod")
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "earshot-prod-api-5xx-rate",
            "Threshold": 1,
            "Metrics": Match.array_with(
                [Match.object_like({"Expression": monitoring_module.API_5XX_RATE_EXPRESSION})]
            ),
        },
    )
    _, without_api = build("prod", with_api=False)
    assert alarm_names(without_api) == BASE_ALARMS - {"earshot-prod-api-5xx-rate"}


def test_hot_queue_age_alarm_is_in_the_pipeline_and_references_base_by_arn():
    template = build_pipeline("prod")
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "earshot-prod-hot-queue-age",
            "MetricName": "ApproximateAgeOfOldestMessage",
            "Namespace": "AWS/SQS",
            "Dimensions": [{"Name": "QueueName", "Value": "earshot-prod-hot"}],
            "Threshold": 60,
            "AlarmActions": [f"arn:aws:sns:us-east-1:{ACCOUNT}:earshot-prod-ops-alerts"],
        },
    )


def test_prod_stacks_stay_decoupled():
    """The pipeline alarm must not create a CloudFormation import from base (CONTEXT §5)."""
    app = cdk.App()
    cfg = StageConfig(stage="prod", account=ACCOUNT)
    env = cdk.Environment(account=ACCOUNT, region=cfg.region)
    base = Template.from_stack(BaseStack(app, cfg.stack_name("base"), cfg=cfg, env=env))
    pipeline = Template.from_stack(PipelineStack(app, cfg.stack_name("pipeline"), cfg=cfg, env=env))
    assert "Fn::ImportValue" not in json.dumps(pipeline.to_json())
    assert all("Export" not in o for o in base.to_json().get("Outputs", {}).values())
    assert alarm_names(base) == BASE_ALARMS
    assert alarm_names(pipeline) == {"earshot-prod-hot-queue-age"}


def test_stays_inside_the_cloudwatch_free_tier():
    monitoring, _ = build("prod")
    assert monitoring.dashboard_metric_count <= monitoring_module.FREE_DASHBOARD_METRICS
    assert monitoring.alarm_metric_count <= monitoring_module.FREE_ALARM_METRICS
    # 5 base alarms + the pipeline one; the 5xx alarm uses 2 metrics.
    assert monitoring.alarm_metric_count == 7


def test_dashboard_shows_exactly_the_allowed_custom_metrics():
    assert set(monitoring_module.CUSTOM_METRICS) == log.ALLOWED_METRICS
    assert len(monitoring_module.CUSTOM_METRICS) == len(log.ALLOWED_METRICS)
    assert monitoring_module.CUSTOM_NAMESPACE == log.NAMESPACE

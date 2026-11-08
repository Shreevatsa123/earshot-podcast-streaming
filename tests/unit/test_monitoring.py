"""Monitoring construct (M6-05). Skipped when aws-cdk-lib isn't installed (run ``make install``)."""

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk import aws_apigatewayv2 as apigwv2  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs import monitoring as monitoring_module  # noqa: E402
from earshot_infra.constructs.core import Core  # noqa: E402
from earshot_infra.constructs.monitoring import Monitoring  # noqa: E402
from shared import log  # noqa: E402

ACCOUNT = "123456789012"


def build(with_api: bool) -> tuple[Monitoring, Template]:
    app = cdk.App()
    cfg = StageConfig(stage="dev", account=ACCOUNT)
    stack = cdk.Stack(app, "MonitoringTest", env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    core = Core(stack, "Core", cfg=cfg)
    http_api = apigwv2.HttpApi(stack, "Api") if with_api else None
    monitoring = Monitoring(stack, "Monitoring", cfg=cfg, core=core, http_api=http_api)
    return monitoring, Template.from_stack(stack)


def test_dashboard_is_named_after_the_stage():
    _, template = build(with_api=False)
    template.resource_count_is("AWS::CloudWatch::Dashboard", 1)
    template.has_resource_properties("AWS::CloudWatch::Dashboard", {"DashboardName": "earshot-dev"})


def test_every_alarm_emails_ops_and_ignores_missing_data():
    _, template = build(with_api=True)
    (ops_topic_id,) = template.find_resources(
        "AWS::SNS::Topic", {"Properties": {"TopicName": "earshot-dev-ops-alerts"}}
    )
    alarms = template.find_resources("AWS::CloudWatch::Alarm")
    assert len(alarms) == 6
    for alarm in alarms.values():
        props = alarm["Properties"]
        assert props["AlarmActions"] == [{"Ref": ops_topic_id}]
        assert props["TreatMissingData"] == "notBreaching"
        assert props["AlarmName"].startswith("earshot-dev-")


def test_api_alarm_only_once_the_api_exists():
    _, without_api = build(with_api=False)
    without_api.resource_count_is("AWS::CloudWatch::Alarm", 5)

    _, with_api = build(with_api=True)
    with_api.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {
            "AlarmName": "earshot-dev-api-5xx-rate",
            "Metrics": Match.array_with(
                [Match.object_like({"Expression": monitoring_module.API_5XX_RATE_EXPRESSION})]
            ),
        },
    )


def test_stays_inside_the_cloudwatch_free_tier():
    monitoring, _ = build(with_api=True)
    assert monitoring.dashboard_metric_count <= monitoring_module.FREE_DASHBOARD_METRICS
    assert monitoring.alarm_metric_count <= monitoring_module.FREE_ALARM_METRICS
    assert len(monitoring.alarms) <= 10


def test_dashboard_shows_exactly_the_allowed_custom_metrics():
    assert set(monitoring_module.CUSTOM_METRICS) == log.ALLOWED_METRICS
    assert len(monitoring_module.CUSTOM_METRICS) == len(log.ALLOWED_METRICS)
    assert monitoring_module.CUSTOM_NAMESPACE == log.NAMESPACE

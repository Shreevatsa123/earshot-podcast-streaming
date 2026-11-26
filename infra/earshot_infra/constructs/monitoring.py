"""CloudWatch dashboard and alarms.

Owner: M6 · Stacks: base (``Monitoring``) and pipeline (``MonitoringPipeline``) · Tracker: M6-05
Spec: CONTEXT §10 "Dashboard", "Alarms"

Creates:
- Dashboard ``cfg.dashboard`` (``earshot-<stage>``), every stage: alarm status, API
  requests/5xx/p95 latency, Lambda errors/throttles/duration for the 5 functions, both
  queues (sent, visible, oldest message age), both DLQs, DynamoDB capacity and throttles,
  and the 8 custom metrics.
- Alarms, **prod only**, all notifying the ops topic:
  - base: processor DLQ not empty, archiver DLQ not empty, API 5xx rate > 1 % (5 min),
    any Lambda throttles, archiver errors.
  - pipeline: hot queue oldest message > 60 s. It lives in the pipeline stack so it only
    exists while the processor's trigger does; otherwise it would fire every time the
    pipeline is down and events wait in the queue.

Why prod only: the CloudWatch free tier covers 10 alarm metrics per account, and these
alarms use 7. Any extra stage in the shared account (CONTEXT §5 prod rule 4) would push it
over. Dashboards are free up to 3 per account, so every stage still gets one.

Metrics are built from deterministic names (``cfg.function_name(...)``, ``cfg.hot_queue``,
…), not from other constructs, so this works whatever state they're in. A resource that
isn't deployed shows "no data", and its alarm stays OK. The one exception is the HTTP API:
its metrics need the generated API id, so ``http_api`` is passed in.

Free-tier budget, checked at synth time: at most 50 metrics on the dashboard and 10 alarm
metrics in total (a metric-math alarm counts every metric it uses).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_sns as sns
from constructs import Construct

from earshot_infra.config import StageConfig, names
from earshot_infra.constructs.core import Core

PERIOD = Duration.minutes(5)

#: CloudWatch free tier, per account per month: 3 dashboards of up to 50 metrics each,
#: and 10 standard-resolution alarm metrics.
FREE_DASHBOARD_METRICS = 50
FREE_ALARM_METRICS = 10

#: Namespace of the custom metrics (must match ``services/shared/log.py``).
CUSTOM_NAMESPACE = "Earshot"

#: The 8 custom metrics from CONTEXT §10, in display order. A fixed tuple, not the set in
#: ``shared/log.py``: set order changes between runs, which would change the dashboard on
#: every deploy. A unit test checks both lists match.
PIPELINE_METRICS = ("EventsAccepted", "EventsRejected", "PlaysCounted", "DuplicateEvents", "StaleEvents")
OUTCOME_METRICS = ("QoEAlertsSent", "HomeFallback", "RecsUsersWritten")
CUSTOM_METRICS = PIPELINE_METRICS + OUTCOME_METRICS

HOT_QUEUE_AGE_LIMIT_S = 60
API_5XX_RATE_LIMIT_PCT = 1
API_5XX_RATE_EXPRESSION = "IF(requests > 0, 100 * errors / requests, 0)"

#: Alarm metrics used by the pipeline stack's alarm, counted against the free tier here.
PIPELINE_ALARM_METRICS = 1


def hot_queue_age_alarm_name(cfg: StageConfig) -> str:
    return f"{cfg.prefix}-hot-queue-age"


def _metric(
    namespace: str, name: str, dimensions: Mapping[str, str], statistic: str, label: str
) -> cw.Metric:
    return cw.Metric(
        namespace=namespace,
        metric_name=name,
        dimensions_map=dict(dimensions),
        statistic=statistic,
        period=PERIOD,
        label=label,
    )


def _queue_metric(queue: str, name: str, statistic: str, label: str) -> cw.Metric:
    return _metric("AWS/SQS", name, {"QueueName": queue}, statistic, label)


def _alarm(
    scope: Construct,
    construct_id: str,
    *,
    cfg: StageConfig,
    action: cw.IAlarmAction,
    short_name: str,
    description: str,
    metric: cw.IMetric,
    threshold: float,
) -> cw.Alarm:
    alarm = cw.Alarm(
        scope,
        construct_id,
        alarm_name=f"{cfg.prefix}-{short_name}",
        alarm_description=description,
        metric=metric,
        threshold=threshold,
        evaluation_periods=1,
        comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
        # No data (e.g. nothing deployed yet, or no traffic) is normal, not an alarm.
        treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
    )
    alarm.add_alarm_action(action)
    return alarm


class Monitoring(Construct):
    """Base stack: the dashboard, plus the base alarms in prod."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: StageConfig,
        core: Core,
        http_api: apigwv2.IHttpApi | None = None,
    ) -> None:
        super().__init__(scope, construct_id)
        self._cfg = cfg
        self.alarms: list[cw.Alarm] = []
        self.alarm_metric_count = 0
        self.dashboard_metric_count = 0

        visible = "ApproximateNumberOfMessagesVisible"
        processor_dlq = _queue_metric(cfg.processor_dlq, visible, "Maximum", "processor DLQ")
        archiver_dlq = _queue_metric(cfg.archiver_dlq, visible, "Maximum", "archiver DLQ")
        # No dimensions = all Lambda functions in the account.
        all_throttles = _metric("AWS/Lambda", "Throttles", {}, "Sum", "all functions")
        archiver_errors = _metric(
            "AWS/Lambda", "Errors", {"FunctionName": cfg.function_name("archiver")}, "Sum", "archiver"
        )

        # ---- Alarms (CONTEXT §10), prod only ----------------------------------------------
        if cfg.is_prod:
            action = cw_actions.SnsAction(core.ops_topic)

            def add(construct_id: str, metric_count: int = 1, **kwargs) -> None:
                self.alarms.append(_alarm(self, construct_id, cfg=cfg, action=action, **kwargs))
                self.alarm_metric_count += metric_count

            add(
                "ProcessorDlqNotEmpty",
                short_name="processor-dlq-not-empty",
                description=f"Messages the processor gave up on (5 receives) are in {cfg.processor_dlq}. "
                "Read them in SQS to see which events failed.",
                metric=processor_dlq,
                threshold=0,
            )
            add(
                "ArchiverDlqNotEmpty",
                short_name="archiver-dlq-not-empty",
                description=f"Messages the archiver gave up on are in {cfg.archiver_dlq}, so they're "
                "missing from the lake. Read them in SQS.",
                metric=archiver_dlq,
                threshold=0,
            )
            if http_api is not None:
                add(
                    "Api5xxRate",
                    metric_count=2,
                    short_name="api-5xx-rate",
                    description="More than 1 % of API requests returned 5xx in 5 minutes. "
                    "Check the API Lambda's errors and logs.",
                    metric=cw.MathExpression(
                        expression=API_5XX_RATE_EXPRESSION,
                        using_metrics={
                            "errors": http_api.metric_server_error(period=PERIOD, statistic="Sum"),
                            "requests": http_api.metric_count(period=PERIOD, statistic="Sum"),
                        },
                        period=PERIOD,
                        label="5xx rate (%)",
                    ),
                    threshold=API_5XX_RATE_LIMIT_PCT,
                )
            add(
                "LambdaThrottles",
                short_name="lambda-throttles",
                description="A Lambda function was throttled. The account concurrency limit may "
                "be too low (make account-check).",
                metric=all_throttles,
                threshold=0,
            )
            add(
                "ArchiverErrors",
                short_name="archiver-errors",
                description="The archiver failed. Its batch is retried, but check its logs: events "
                "only reach Athena through it.",
                metric=archiver_errors,
                threshold=0,
            )
            self.alarm_metric_count += PIPELINE_ALARM_METRICS

        # ---- Dashboard (CONTEXT §10) ---------------------------------------------------
        dashboard = cw.Dashboard(self, "Dashboard", dashboard_name=cfg.dashboard)
        if cfg.is_prod:
            hot_queue_age = cw.Alarm.from_alarm_arn(
                self,
                "HotQueueAgeAlarm",
                f"arn:aws:cloudwatch:{cfg.region}:{cfg.account}:alarm:{hot_queue_age_alarm_name(cfg)}",
            )
            dashboard.add_widgets(
                cw.AlarmStatusWidget(
                    alarms=[*self.alarms, hot_queue_age], title="Alarms (hot queue age: pipeline stack)",
                    width=24, height=3,
                )
            )
        else:
            dashboard.add_widgets(
                cw.TextWidget(
                    markdown="**Alarms:** only created in `prod`, to stay inside the CloudWatch "
                    "free tier (10 alarm metrics per account).",
                    width=24,
                    height=2,
                )
            )

        if http_api is not None:
            requests = http_api.metric_count(period=PERIOD, statistic="Sum", label="requests")
            errors = http_api.metric_server_error(period=PERIOD, statistic="Sum", label="5xx")
            latency = http_api.metric_latency(period=PERIOD, statistic="p95", label="p95")
            dashboard.add_widgets(
                self._graph("API requests", [requests]),
                self._graph("API 5xx", [errors]),
                self._graph("API latency p95 (ms)", [latency]),
            )

        def per_function(metric_name: str, statistic: str) -> list[cw.IMetric]:
            return [
                _metric("AWS/Lambda", metric_name, {"FunctionName": cfg.function_name(fn)}, statistic, fn)
                for fn in names.FUNCTIONS
            ]

        dashboard.add_widgets(
            self._graph("Lambda errors", per_function("Errors", "Sum")),
            self._graph("Lambda throttles", per_function("Throttles", "Sum")),
            self._graph("Lambda duration p95 (ms)", per_function("Duration", "p95")),
        )

        oldest = "ApproximateAgeOfOldestMessage"

        def both_queues(metric_name: str, statistic: str) -> list[cw.IMetric]:
            return [
                _queue_metric(cfg.hot_queue, metric_name, statistic, "hot"),
                _queue_metric(cfg.cold_queue, metric_name, statistic, "cold"),
            ]

        dashboard.add_widgets(
            self._graph("Queues: messages sent", both_queues("NumberOfMessagesSent", "Sum")),
            self._graph("Queues: messages waiting", both_queues(visible, "Maximum")),
            self._graph("Queues: oldest message (s)", both_queues(oldest, "Maximum")),
        )

        table = {"TableName": cfg.table_name}
        dashboard.add_widgets(
            self._graph(
                "DynamoDB consumed capacity",
                [
                    _metric("AWS/DynamoDB", "ConsumedReadCapacityUnits", table, "Sum", "read"),
                    _metric("AWS/DynamoDB", "ConsumedWriteCapacityUnits", table, "Sum", "write"),
                ],
            ),
            self._graph(
                "DynamoDB throttles",
                [
                    _metric("AWS/DynamoDB", "ReadThrottleEvents", table, "Sum", "read"),
                    _metric("AWS/DynamoDB", "WriteThrottleEvents", table, "Sum", "write"),
                ],
            ),
            self._graph("Dead-letter queues", [processor_dlq, archiver_dlq]),
        )

        def custom(metric_names: Sequence[str]) -> list[cw.IMetric]:
            return [_metric(CUSTOM_NAMESPACE, n, {"Stage": cfg.stage}, "Sum", n) for n in metric_names]

        dashboard.add_widgets(
            self._graph("Ingest and processing (custom)", custom(PIPELINE_METRICS), width=12),
            self._graph("Alerts, fallbacks and recs (custom)", custom(OUTCOME_METRICS), width=12),
        )
        self.dashboard = dashboard

        if self.dashboard_metric_count > FREE_DASHBOARD_METRICS:
            raise ValueError(
                f"The dashboard has {self.dashboard_metric_count} metrics; the free tier "
                f"covers {FREE_DASHBOARD_METRICS}. Remove some before adding more."
            )
        if self.alarm_metric_count > FREE_ALARM_METRICS:
            raise ValueError(
                f"The alarms use {self.alarm_metric_count} metrics; the free tier covers "
                f"{FREE_ALARM_METRICS}. Each extra alarm metric costs $0.10/month."
            )

    def _graph(self, title: str, metrics: Sequence[cw.IMetric], *, width: int = 8) -> cw.GraphWidget:
        self.dashboard_metric_count += len(metrics)
        return cw.GraphWidget(title=title, left=list(metrics), width=width, height=6)


class MonitoringPipeline(Construct):
    """Pipeline stack: the hot queue age alarm (prod only), so it exists only while the
    processor's trigger does. The ops topic is referenced by ARN (CONTEXT §5)."""

    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        self.alarm: cw.Alarm | None = None
        if not cfg.is_prod:
            return
        ops_topic = sns.Topic.from_topic_arn(self, "OpsTopic", cfg.ops_topic_arn)
        self.alarm = _alarm(
            self,
            "HotQueueAge",
            cfg=cfg,
            action=cw_actions.SnsAction(ops_topic),
            short_name="hot-queue-age",
            description=f"The oldest message in {cfg.hot_queue} is more than {HOT_QUEUE_AGE_LIMIT_S} s "
            "old: the processor is falling behind or failing. Check its errors and throttles on "
            "the dashboard.",
            metric=_queue_metric(cfg.hot_queue, "ApproximateAgeOfOldestMessage", "Maximum", "hot queue"),
            threshold=HOT_QUEUE_AGE_LIMIT_S,
        )

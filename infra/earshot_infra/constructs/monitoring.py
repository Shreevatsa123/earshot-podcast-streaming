"""CloudWatch dashboard and alarms.

Owner: M6 · Stack: base · Tracker: M6-05 · Spec: CONTEXT §10 "Dashboard", "Alarms"

Creates:
- Dashboard ``cfg.dashboard`` (``earshot-<stage>``): alarm status, API, Lambda, stream and
  lake, DynamoDB, and the 8 custom metrics.
- 6 alarms, all notifying ``core.ops_topic``: processor iterator age > 60 s, DLQ not empty,
  API 5xx rate > 1 %, any Lambda throttles, Firehose S3 delivery failures, Firehose Parquet
  conversion failures. The API alarm only exists once the HTTP API does (see below).

Metrics are built from deterministic names (``cfg.function_name(...)``, ``cfg.stream_name``,
…), not from other constructs, so this works whatever state they're in. A resource that
isn't deployed (e.g. while the pipeline stack is down) shows "no data", and its alarms stay
OK. The one exception is the HTTP API: its metrics need the generated API id, so the API row
and the 5xx alarm appear once M2's ``Api`` construct sets ``http_api``.

Free-tier budget, checked at synth time: at most 50 metrics on the dashboard and 10 alarm
metrics in total (a metric-math alarm counts every metric it uses). Going over costs money.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
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

ITERATOR_AGE_LIMIT_MS = 60_000
API_5XX_RATE_LIMIT_PCT = 1
API_5XX_RATE_EXPRESSION = "IF(requests > 0, 100 * errors / requests, 0)"


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


class Monitoring(Construct):
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
        self._action = cw_actions.SnsAction(core.ops_topic)
        self.alarms: list[cw.Alarm] = []
        self.alarm_metric_count = 0
        self.dashboard_metric_count = 0

        processor = {"FunctionName": cfg.function_name("processor")}
        stream = {"StreamName": cfg.stream_name}
        firehose = {"DeliveryStreamName": cfg.firehose_name}
        table = {"TableName": cfg.table_name}

        processor_lag = _metric("AWS/Lambda", "IteratorAge", processor, "Maximum", "processor")
        dlq_depth = _metric(
            "AWS/SQS", "ApproximateNumberOfMessagesVisible", {"QueueName": cfg.processor_dlq},
            "Maximum", "messages",
        )
        # No dimensions = all Lambda functions in the account.
        all_throttles = _metric("AWS/Lambda", "Throttles", {}, "Sum", "all functions")
        s3_success = _metric("AWS/Firehose", "DeliveryToS3.Success", firehose, "Minimum", "success")
        failed_conversion = _metric(
            "AWS/Firehose", "FailedConversion.Records", firehose, "Sum", "failed Parquet conversion"
        )

        # ---- Alarms (CONTEXT §10) ------------------------------------------------------
        self._alarm(
            "ProcessorIteratorAge",
            short_name="processor-iterator-age",
            description="The processor is more than 60 s behind the Kinesis stream. "
            "Check processor errors and throttles on the dashboard.",
            metric=processor_lag,
            threshold=ITERATOR_AGE_LIMIT_MS,
            comparison=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        self._alarm(
            "DlqNotEmpty",
            short_name="processor-dlq-not-empty",
            description="Kinesis batches the processor gave up on are in the DLQ. Read them "
            f"in SQS ({cfg.processor_dlq}) to see which records failed.",
            metric=dlq_depth,
            threshold=0,
            comparison=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        if http_api is not None:
            error_rate = cw.MathExpression(
                expression=API_5XX_RATE_EXPRESSION,
                using_metrics={
                    "errors": http_api.metric_server_error(period=PERIOD, statistic="Sum"),
                    "requests": http_api.metric_count(period=PERIOD, statistic="Sum"),
                },
                period=PERIOD,
                label="5xx rate (%)",
            )
            self._alarm(
                "Api5xxRate",
                short_name="api-5xx-rate",
                description="More than 1 % of API requests returned 5xx in 5 minutes. "
                "Check the API Lambda's errors and logs.",
                metric=error_rate,
                threshold=API_5XX_RATE_LIMIT_PCT,
                comparison=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
                metric_count=2,
            )
        self._alarm(
            "LambdaThrottles",
            short_name="lambda-throttles",
            description="A Lambda function was throttled. The account concurrency limit may "
            "be too low (make account-check).",
            metric=all_throttles,
            threshold=0,
            comparison=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )
        self._alarm(
            "FirehoseDeliveryFailed",
            short_name="firehose-delivery-failed",
            description="Firehose failed to write to the lake bucket.",
            metric=s3_success,
            threshold=1,
            comparison=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
        )
        self._alarm(
            "FirehoseConversionFailed",
            short_name="firehose-conversion-failed",
            description="Some events didn't match the Glue table and went to errors/ in the "
            "lake instead of events/ (they're missing from Athena).",
            metric=failed_conversion,
            threshold=0,
            comparison=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        # ---- Dashboard (CONTEXT §10) ---------------------------------------------------
        dashboard = cw.Dashboard(self, "Dashboard", dashboard_name=cfg.dashboard)
        dashboard.add_widgets(
            cw.AlarmStatusWidget(alarms=self.alarms, title="Alarms", width=24, height=3)
        )

        if http_api is not None:
            dashboard.add_widgets(
                self._graph(
                    "API requests",
                    [http_api.metric_count(period=PERIOD, statistic="Sum", label="requests")],
                ),
                self._graph(
                    "API errors",
                    [
                        http_api.metric_client_error(period=PERIOD, statistic="Sum", label="4xx"),
                        http_api.metric_server_error(period=PERIOD, statistic="Sum", label="5xx"),
                    ],
                ),
                self._graph(
                    "API latency p95 (ms)",
                    [http_api.metric_latency(period=PERIOD, statistic="p95", label="p95")],
                ),
            )
        else:
            dashboard.add_widgets(
                cw.TextWidget(
                    markdown="**API:** not deployed yet. The API graphs and the 5xx alarm "
                    "appear once M2's `Api` construct sets `http_api` (M2-04).",
                    width=24,
                    height=2,
                )
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
        dashboard.add_widgets(
            self._graph(
                "Kinesis incoming records",
                [_metric("AWS/Kinesis", "IncomingRecords", stream, "Sum", "records")],
            ),
            self._graph(
                "Iterator age (ms)",
                [
                    _metric(
                        "AWS/Kinesis", "GetRecords.IteratorAgeMilliseconds", stream, "Maximum",
                        "stream (all consumers)",
                    ),
                    processor_lag,
                ],
            ),
            self._graph(
                "Firehose -> S3 records",
                [
                    _metric("AWS/Firehose", "DeliveryToS3.Records", firehose, "Sum", "delivered"),
                    failed_conversion,
                ],
            ),
        )
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
            self._graph("Processor DLQ", [dlq_depth]),
        )

        def custom(metric_names: Sequence[str]) -> list[cw.IMetric]:
            return [
                _metric(CUSTOM_NAMESPACE, n, {"Stage": cfg.stage}, "Sum", n) for n in metric_names
            ]

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

    def _graph(
        self, title: str, metrics: Sequence[cw.IMetric], *, width: int = 8
    ) -> cw.GraphWidget:
        self.dashboard_metric_count += len(metrics)
        return cw.GraphWidget(title=title, left=list(metrics), width=width, height=6)

    def _alarm(
        self,
        construct_id: str,
        *,
        short_name: str,
        description: str,
        metric: cw.IMetric,
        threshold: float,
        comparison: cw.ComparisonOperator,
        metric_count: int = 1,
    ) -> cw.Alarm:
        alarm = cw.Alarm(
            self,
            construct_id,
            alarm_name=f"{self._cfg.prefix}-{short_name}",
            alarm_description=description,
            metric=metric,
            threshold=threshold,
            evaluation_periods=1,
            comparison_operator=comparison,
            # No data (e.g. the pipeline stack is down) is normal, not an alarm.
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
        alarm.add_alarm_action(self._action)
        self.alarms.append(alarm)
        self.alarm_metric_count += metric_count
        return alarm

"""Archiver: the cold queue, its DLQ and the Lambda (base), and its SQS trigger (pipeline).

Replaces Amazon Data Firehose, which Free plan accounts can't use. The archiver collects
events from the cold queue and writes gzipped JSON Lines files to the lake.

Owner: M5 · Tracker: M5-02 · Spec: CONTEXT §9 (lake layout, Glue table), §10 "Event queues", "Archiver"
"""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from earshot_infra.common import python_function
from earshot_infra.config import StageConfig, names
from earshot_infra.constructs.core import Core

# Queue settings (CONTEXT §10 "Event queues").
#: Events wait this long while the pipeline (the trigger) is down.
RETENTION = Duration.days(14)
#: At least 6x the function timeout plus the batching window: 6 x 60 s + 60 s = 420 s.
VISIBILITY_TIMEOUT = Duration.seconds(900)
#: A message that fails this many times moves to the DLQ (alarmed by M6).
MAX_RECEIVE_COUNT = 5

# Function and trigger settings (CONTEXT §10 "Archiver", "SQS triggers").
FUNCTION_TIMEOUT_SECONDS = 60
BATCH_SIZE = 1000
BATCHING_WINDOW = Duration.seconds(60)
MAX_CONCURRENCY = 2


class ArchiverBase(Construct):
    """Cold queue, its DLQ, the subscription and the archiver function. Stack: base.

    - SQS queue ``cfg.cold_queue``: SQS-managed encryption (SNS can't deliver to queues
      using the AWS-managed KMS key), 14-day retention, 900 s visibility timeout, redrive
      to DLQ ``cfg.archiver_dlq`` after 5 receives. Both are DESTROYed with the stack.
    - Subscription of the queue to ``topic`` with **raw message delivery**, so each SQS
      body is exactly ``{"events": [...]}``. Without it every message arrives wrapped in
      an SNS envelope and the archiver would reject them all. Skipped if ``topic`` is None.
    - ``earshot-<stage>-archiver`` (60 s timeout, env ``LAKE_BUCKET``), allowed to write
      only under ``events/`` in the lake bucket and to consume the cold queue. The
      pipeline imports this function by ARN, so every permission is granted here.

    Exposes (keep these names): ``function``, ``queue``, ``dlq``.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: StageConfig,
        core: Core,
        topic: sns.ITopic | None,
    ) -> None:
        super().__init__(scope, construct_id)

        dlq = sqs.Queue(
            self,
            "Dlq",
            queue_name=cfg.archiver_dlq,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=RETENTION,
            removal_policy=RemovalPolicy.DESTROY,
        )
        queue = sqs.Queue(
            self,
            "Queue",
            queue_name=cfg.cold_queue,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=RETENTION,
            visibility_timeout=VISIBILITY_TIMEOUT,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=MAX_RECEIVE_COUNT, queue=dlq),
            removal_policy=RemovalPolicy.DESTROY,
        )
        if topic is not None:
            topic.add_subscription(subscriptions.SqsSubscription(queue, raw_message_delivery=True))

        function = python_function(
            self,
            "Function",
            cfg=cfg,
            name="archiver",
            handler="archiver.handler.main",
            environment={"LAKE_BUCKET": cfg.lake_bucket},
            timeout_seconds=FUNCTION_TIMEOUT_SECONDS,
            description="Cold queue -> gzipped JSON Lines in the lake, one file per server_ts hour",
        )
        core.lake_bucket.grant_put(function, f"{names.LAKE_EVENTS_PREFIX}*")
        queue.grant_consume_messages(function)

        self.function: lambda_.IFunction | None = function
        self.queue: sqs.IQueue | None = queue
        self.dlq: sqs.IQueue | None = dlq


class ArchiverPipeline(Construct):
    """Cold queue -> archiver trigger (SQS event source mapping). Stack: **pipeline**.

    STATUS: STUB. Comes in the next commit.
    """

    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        # TODO(M5-02): the SQS trigger with the CONTEXT §10 settings.

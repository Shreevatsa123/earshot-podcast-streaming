"""Archiver: the cold queue, its DLQ and the Lambda (base), and its SQS trigger (pipeline).

Replaces Amazon Data Firehose, which Free plan accounts can't use. The archiver collects
events from the cold queue and writes gzipped JSON Lines files to the lake.

Owner: M5 · Tracker: M5-02 · Spec: CONTEXT §9 (lake layout, Glue table), §10 "Event queues", "Archiver"

STATUS: STUB. Both classes create nothing yet.
"""

from __future__ import annotations

from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class ArchiverBase(Construct):
    """Cold queue, its DLQ, the subscription and the archiver function. Stack: base.

    Must create:
    - SQS queue ``cfg.cold_queue`` with the CONTEXT §10 queue settings: SQS-managed
      encryption (``sqs.QueueEncryption.SQS_MANAGED``), 14-day retention, 900 s visibility
      timeout, and a redrive policy to DLQ ``cfg.archiver_dlq`` after 5 receives (DLQ: same
      encryption, 14-day retention). ``removal_policy=RemovalPolicy.DESTROY`` on both.
    - Subscription of the queue to ``topic`` with **raw message delivery**
      (``subscriptions.SqsSubscription(queue, raw_message_delivery=True)``).
    - ``common.python_function(name="archiver", handler="archiver.handler.main",
      timeout_seconds=60)`` with env ``LAKE_BUCKET``. Grant it write on
      ``core.lake_bucket`` (the ``events/*`` prefix is enough) and
      ``queue.grant_consume_messages(function)``. The pipeline imports this function by
      ARN, so every permission is granted here.

    Inputs: ``core``; ``topic`` from ``EventsTopic`` (None until M3-03; skip the
    subscription if so).
    Exposes (keep these names): ``function``, ``queue``, ``dlq``. Each is None until implemented.
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
        self.function: lambda_.IFunction | None = None
        self.queue: sqs.IQueue | None = None
        self.dlq: sqs.IQueue | None = None
        # TODO(M5-02): implement per the docstring.


class ArchiverPipeline(Construct):
    """Cold queue -> archiver trigger (SQS event source mapping). Stack: **pipeline**.

    Must create:
    - ``lambda_.EventSourceMapping`` from ``cfg.cold_queue_arn`` to the archiver imported
      **by ARN** (``lambda_.Function.from_function_arn(self, "Archiver",
      cfg.function_arn("archiver"))``). Settings from CONTEXT §10: batch size 1000,
      batching window 60 s, report batch item failures, maximum concurrency 2.

    Lambda polls the queue even when it's empty, which is why this lives in the pipeline
    stack and comes down after each session.
    Exposes: nothing.
    """

    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        # TODO(M5-02): implement per the docstring.

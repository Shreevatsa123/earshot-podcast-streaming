"""Stream processor: the hot queue, its DLQ and the Lambda (base), and its SQS trigger (pipeline).

Owner: M4 · Tracker: M4-05 (construct), M4-01..M4-04 (code) · Spec: CONTEXT §8.2, §10

STATUS: STUB. Both classes create nothing yet.
"""

from __future__ import annotations

from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class ProcessingBase(Construct):
    """Hot queue, its DLQ, the subscription and the processor function. Stack: base.

    Must create:
    - SQS queue ``cfg.hot_queue`` with the CONTEXT §10 queue settings: SQS-managed
      encryption (``sqs.QueueEncryption.SQS_MANAGED``; SNS can't deliver to the AWS-managed
      KMS key), 14-day retention, 300 s visibility timeout, and a redrive policy to DLQ
      ``cfg.processor_dlq`` after 5 receives (DLQ: same encryption, 14-day retention).
      ``removal_policy=RemovalPolicy.DESTROY`` on both.
    - Subscription of the queue to ``topic`` with **raw message delivery**
      (``subscriptions.SqsSubscription(queue, raw_message_delivery=True)``).
    - ``common.python_function(name="processor", handler="processor.handler.main")`` with
      env ``TABLE_NAME``, ``QOE_TOPIC_ARN`` and ``QOE_THRESHOLD`` (default ``30``).
      Grant read/write on ``core.table``, publish on ``core.qoe_topic`` and
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
        # TODO(M4-05): implement per the docstring.


class ProcessingPipeline(Construct):
    """Hot queue -> processor trigger (SQS event source mapping). Stack: **pipeline**.

    Must create:
    - ``lambda_.EventSourceMapping`` from ``cfg.hot_queue_arn`` to the processor imported
      **by ARN** (``lambda_.Function.from_function_arn(self, "Processor",
      cfg.function_arn("processor"))``). Settings from CONTEXT §10: batch size 100,
      batching window 1 s, report batch item failures, maximum concurrency 5.

    Lambda polls the queue even when it's empty, which is why this lives in the pipeline
    stack and comes down after each session.
    Exposes: nothing.
    """

    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        # TODO(M4-05): implement per the docstring.

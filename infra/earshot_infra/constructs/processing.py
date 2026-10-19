"""Stream processor: the Lambda + DLQ (base) and its Kinesis trigger (pipeline).

Owner: M4 · Tracker: M4-05 (construct), M4-01..M4-04 (code) · Spec: CONTEXT §8.2, §10

STATUS: STUB. Both classes create nothing yet.
"""

from __future__ import annotations

from aws_cdk import aws_kinesis as kinesis
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class ProcessingBase(Construct):
    """Processor function and DLQ. Stack: base.

    Must create:
    - ``common.python_function(name="processor", handler="processor.handler.main")`` with
      env ``TABLE_NAME``, ``QOE_TOPIC_ARN`` and ``QOE_THRESHOLD`` (default ``30``).
      Grant read/write on ``core.table`` and publish on ``core.qoe_topic``.
    - SQS queue ``cfg.processor_dlq`` (the event source mapping's on-failure
      destination). Grant the function ``sqs:SendMessage`` on it here.
    - Kinesis read permissions **on** ``cfg.stream_arn``, granted here in base
      (``kinesis:DescribeStream``, ``DescribeStreamSummary``, ``GetRecords``,
      ``GetShardIterator``, ``ListShards``, ``SubscribeToShard``). The pipeline imports
      this function by ARN, so it can't add to the function's role.

    Exposes (keep these names): ``function``, ``dlq``. Each is None until implemented.
    """

    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core) -> None:
        super().__init__(scope, construct_id)
        self.function: lambda_.IFunction | None = None
        self.dlq: sqs.IQueue | None = None
        # TODO(M4-05): implement per the docstring.


class ProcessingPipeline(Construct):
    """Kinesis -> processor event source mapping. Stack: **pipeline**.

    Must create:
    - ``lambda_.EventSourceMapping`` from ``stream`` to the processor, imported **by ARN**
      with ``lambda_.Function.from_function_arn(self, "Processor", cfg.function_arn("processor"))``.
      Settings from CONTEXT §10: batch size 100, batching window 1 s, ``TRIM_HORIZON``,
      parallelization factor 1, report batch item failures, bisect on error, 5 retries,
      max record age 3600 s, on-failure destination = the DLQ imported by
      ``cfg.processor_dlq_arn``.

    Inputs: ``stream`` from ``Stream`` (None until M3-03; skip the mapping if so).
    Exposes: nothing.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: StageConfig,
        stream: kinesis.IStream | None,
    ) -> None:
        super().__init__(scope, construct_id)
        # TODO(M4-05): implement per the docstring.

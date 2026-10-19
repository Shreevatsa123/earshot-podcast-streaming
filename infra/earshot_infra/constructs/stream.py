"""Kinesis data stream for playback events.

Owner: M3 · Stack: **pipeline** (hourly-billed, ~$0.015/shard-hour) · Tracker: M3-03 · Spec: CONTEXT §5, §10

STATUS: STUB. Creates nothing yet.

Must create:
- ``kinesis.Stream`` named ``cfg.stream_name``: provisioned mode, 1 shard, 24 h retention,
  ``encryption=kinesis.StreamEncryption.MANAGED`` (the free AWS-managed key; no
  customer-managed KMS keys, CONTEXT §0).

Exposes (keep this name; ``ProcessingPipeline`` and ``Firehose`` read it):
- ``stream``. None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_kinesis as kinesis
from constructs import Construct

from earshot_infra.config import StageConfig


class Stream(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        self.stream: kinesis.IStream | None = None
        # TODO(M3-03): implement per the docstring.

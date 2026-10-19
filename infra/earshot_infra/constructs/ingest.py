"""Ingest Lambda for ``POST /events`` (the function only; M2 wires the route).

Owner: M3 · Stack: base · Tracker: M3-02 · Spec: CONTEXT §7.5

STATUS: STUB. Creates nothing yet.

Must create:
- ``common.python_function(name="ingest", handler="ingest.handler.main")`` with env
  ``STREAM_NAME`` and ``ALLOWED_GENRES``.
- IAM on ``cfg.stream_arn``: ``kinesis:PutRecords`` and ``kinesis:DescribeStreamSummary``.
  The stream lives in the **pipeline** stack, so reference it by name/ARN only, never
  by object (CONTEXT §5). When it doesn't exist, return 503 ``PIPELINE_OFFLINE``.

Exposes (keep this name; ``Api`` reads it):
- ``function``. None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class Ingest(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core) -> None:
        super().__init__(scope, construct_id)
        self.function: lambda_.IFunction | None = None
        # TODO(M3-02): implement per the docstring.

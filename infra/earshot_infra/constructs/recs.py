"""Recommendation batch job: Step Functions -> Athena -> recs writer Lambda.

Owner: M5 · Stack: base · Tracker: M5-04 (writer code), M5-05 (construct) · Spec: CONTEXT §10 "Recommendations"

STATUS: STUB. Creates nothing yet.

Must create:
- Recs writer: ``common.python_function(name="recs-writer",
  handler="recs_writer.handler.main")`` with env ``TABLE_NAME`` and ``LAKE_BUCKET``.
  Grant write on ``core.table`` and read on ``core.lake_bucket``.
- Standard state machine ``cfg.state_machine``: a Parallel state running ``recs.sql``
  and ``popular.sql`` with ``AthenaStartQueryExecution`` (``.sync``, workgroup
  ``cfg.athena_workgroup``, output under ``recs-runs/<run_id>/``), then ``LambdaInvoke``
  of the writer. Output: ``{run_id, users_written, popular_count}``.
- Permissions the workflow needs: Athena on the workgroup, Glue read on the
  ``cfg.glue_*`` ARNs, S3 on the lake bucket.

Inputs: ``core``, and ``lake`` (whose attributes may be None until M5-01).
Exposes (keep these names): ``function``, ``state_machine``. Each is None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core
from earshot_infra.constructs.lake import Lake


class Recs(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core, lake: Lake
    ) -> None:
        super().__init__(scope, construct_id)
        self.function: lambda_.IFunction | None = None
        self.state_machine: sfn.IStateMachine | None = None
        # TODO(M5-05): implement per the docstring.

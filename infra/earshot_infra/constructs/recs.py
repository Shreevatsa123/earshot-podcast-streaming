"""Recommendation batch job: Step Functions -> Athena -> recs writer Lambda.

Owner: M5 · Stack: base · Tracker: M5-04 (writer code), M5-05 (construct) · Spec: CONTEXT §10 "Recommendations"

Creates:
- The recs writer ``earshot-<stage>-recs-writer`` (env ``TABLE_NAME``, ``LAKE_BUCKET``, 120 s
  timeout): may write the table and read only ``recs-runs/`` in the lake.

STATUS: the state machine ``cfg.state_machine`` comes in the next commit.

Exposes (keep these names): ``function``, ``state_machine`` (None until the state machine exists).
"""

from __future__ import annotations

from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct

from earshot_infra.common import python_function
from earshot_infra.config import StageConfig, names
from earshot_infra.constructs.core import Core
from earshot_infra.constructs.lake import Lake

WRITER_TIMEOUT_SECONDS = 120


class Recs(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core, lake: Lake
    ) -> None:
        super().__init__(scope, construct_id)

        writer = python_function(
            self,
            "Writer",
            cfg=cfg,
            name="recs-writer",
            handler="recs_writer.handler.main",
            environment={"TABLE_NAME": cfg.table_name, "LAKE_BUCKET": cfg.lake_bucket},
            timeout_seconds=WRITER_TIMEOUT_SECONDS,
            description="Athena result CSVs -> RECS and POPULAR items (CONTEXT §8.1, §10)",
        )
        core.table.grant_write_data(writer)
        # The writer opens two known result files; it never lists the bucket.
        writer.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[core.lake_bucket.arn_for_objects(f"{names.RECS_RUNS_PREFIX}*")],
            )
        )

        self.function: lambda_.IFunction | None = writer
        self.state_machine: sfn.IStateMachine | None = None

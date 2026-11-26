"""Recommendation batch job: Step Functions -> Athena -> recs writer Lambda.

Owner: M5 · Stack: base · Tracker: M5-04 (writer code), M5-05 (construct) · Spec: CONTEXT §10 "Recommendations"

Creates:
- The recs writer ``earshot-<stage>-recs-writer`` (env ``TABLE_NAME``, ``LAKE_BUCKET``, 120 s
  timeout): may write the table and read only ``recs-runs/`` in the lake.
- The Standard state machine ``earshot-<stage>-recs`` (JSONata), run on demand:
  1. **Prepare**: ``run_id`` = the execution's name; ``end_ms`` = the start time, or the
     optional input ``{"as_of": "<ISO time>"}`` to run "as if it were" another time.
  2. **Queries** (parallel): ``recs.sql`` over 30 days and ``popular.sql`` over 7 days,
     each an Athena ``.sync`` task in workgroup ``earshot-<stage>`` writing to
     ``s3://<lake>/recs-runs/<run_id>/``. The SQL is read from ``athena/*.sql`` at synth
     time, so the files stay the single source.
  3. **Write**: the writer gets ``{run_id, recs_csv, popular_csv}``; its result
     ``{run_id, users_written, popular_count}`` is the job's output (§10).

The Athena steps are plain ``CustomState`` JSON instead of CDK's
``AthenaStartQueryExecution``: that task prefixes ``s3://<bucket>/`` to the output location,
which breaks a per-run JSONata folder, and it grants far more than this job needs (any S3
object, bucket creation, Glue table create/delete). The role here gets only: Athena in
the workgroup, Glue reads of the events table, lake reads under ``events/``, lake writes
under ``recs-runs/``, and invoking the writer.

Start a run: Step Functions console -> ``earshot-<stage>-recs`` -> Start execution, or
``aws stepfunctions start-execution --state-machine-arn <arn> [--input '{"as_of": "..."}']``.

Exposes (keep these names): ``function``, ``state_machine``.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from earshot_infra.common import python_function
from earshot_infra.config import REPO_ROOT, StageConfig, names
from earshot_infra.constructs.core import Core
from earshot_infra.constructs.lake import Lake

ATHENA_DIR = REPO_ROOT / "athena"
RECS_WINDOW_DAYS = 30  # §10: recs.sql reads the last 30 days of plays
POPULAR_WINDOW_DAYS = 7  # §10: popular.sql reads the last 7 days
DAY_MS = 86_400_000
WRITER_TIMEOUT_SECONDS = 120
JOB_TIMEOUT = Duration.minutes(15)
#: Athena throttles StartQueryExecution when too many queries start at once.
ATHENA_RETRY = {
    "ErrorEquals": ["Athena.TooManyRequestsException"],
    "IntervalSeconds": 5,
    "MaxAttempts": 3,
    "BackoffRate": 2,
}


def query_sql(name: str) -> str:
    """The text of ``athena/<name>.sql``, embedded in the state machine at synth time."""
    return (ATHENA_DIR / f"{name}.sql").read_text(encoding="utf-8")


def window_parameters(days: int) -> list[str]:
    """JSONata for the queries' 4 positional parameters, a ``days`` window ending at ``$end_ms``.

    Athena pastes ExecutionParameters into the SQL as literals, so the two dates carry
    their own single quotes and the two numbers don't. ``dt_to`` is the UTC date after the
    window (see the query headers). ``$fromMillis`` formats in UTC.
    """
    date = "'[Y0001]-[M01]-[D01]'"
    return [
        f"{{% \"'\" & $fromMillis($end_ms - {days * DAY_MS}, {date}) & \"'\" %}}",
        f"{{% \"'\" & $fromMillis($end_ms + {DAY_MS}, {date}) & \"'\" %}}",
        f"{{% $string($end_ms - {days * DAY_MS}) %}}",
        "{% $string($end_ms) %}",
    ]


def athena_query_state(cfg: StageConfig, partition: str, *, query: str, days: int) -> dict[str, Any]:
    """An Athena ``.sync`` task (JSONata) that outputs the ``s3://`` path of the result CSV."""
    return {
        "Type": "Task",
        "Resource": f"arn:{partition}:states:::athena:startQueryExecution.sync",
        "Arguments": {
            "QueryString": query_sql(query),
            "QueryExecutionContext": {"Database": cfg.glue_database},
            "WorkGroup": cfg.athena_workgroup,
            "ResultConfiguration": {
                "OutputLocation": f"{{% 's3://{cfg.lake_bucket}/{names.RECS_RUNS_PREFIX}' & $run_id & '/' %}}",
            },
            "ExecutionParameters": window_parameters(days),
        },
        "Retry": [ATHENA_RETRY],
        "Output": "{% $states.result.QueryExecution.ResultConfiguration.OutputLocation %}",
    }


class Recs(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core, lake: Lake
    ) -> None:
        super().__init__(scope, construct_id)
        partition = Stack.of(self).partition

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

        prepare = sfn.Pass.jsonata(
            self,
            "Prepare",
            assign={
                "run_id": "{% $states.context.Execution.Name %}",
                "end_ms": (
                    "{% $exists($states.input.as_of) ? $toMillis($states.input.as_of)"
                    " : $toMillis($states.context.Execution.StartTime) %}"
                ),
            },
        )
        queries = (
            sfn.Parallel.jsonata(self, "Queries")
            .branch(
                sfn.CustomState(
                    self,
                    "RecsQuery",
                    state_json=athena_query_state(cfg, partition, query="recs", days=RECS_WINDOW_DAYS),
                )
            )
            .branch(
                sfn.CustomState(
                    self,
                    "PopularQuery",
                    state_json=athena_query_state(cfg, partition, query="popular", days=POPULAR_WINDOW_DAYS),
                )
            )
        )
        write = tasks.LambdaInvoke.jsonata(
            self,
            "Write",
            lambda_function=writer,
            payload=sfn.TaskInput.from_object(
                {
                    "run_id": "{% $run_id %}",
                    "recs_csv": "{% $states.input[0] %}",
                    "popular_csv": "{% $states.input[1] %}",
                }
            ),
            outputs="{% $states.result.Payload %}",
        )

        state_machine = sfn.StateMachine(
            self,
            "StateMachine",
            state_machine_name=cfg.state_machine,
            state_machine_type=sfn.StateMachineType.STANDARD,
            query_language=sfn.QueryLanguage.JSONATA,
            definition_body=sfn.DefinitionBody.from_chainable(prepare.next(queries).next(write)),
            timeout=JOB_TIMEOUT,
        )
        self._grant_queries(state_machine, cfg, core)

        self.function: lambda_.IFunction | None = writer
        self.state_machine: sfn.IStateMachine | None = state_machine

    @staticmethod
    def _grant_queries(state_machine: sfn.StateMachine, cfg: StageConfig, core: Core) -> None:
        """Exactly what the two Athena steps need, and nothing account-wide."""
        stack = Stack.of(state_machine)
        athena_arn = f"arn:{stack.partition}:athena:{cfg.region}:{cfg.account}"
        bucket = core.lake_bucket
        statements = [
            iam.PolicyStatement(
                actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:StopQueryExecution"],
                resources=[f"{athena_arn}:workgroup/{cfg.athena_workgroup}"],
            ),
            iam.PolicyStatement(
                actions=["athena:GetDataCatalog"],
                resources=[f"{athena_arn}:datacatalog/AwsDataCatalog"],
            ),
            # Athena reads the table definition on every query, projection or not.
            iam.PolicyStatement(
                actions=["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions"],
                resources=[cfg.glue_catalog_arn, cfg.glue_database_arn, cfg.glue_table_arn],
            ),
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"],
                resources=[bucket.bucket_arn],
            ),
            iam.PolicyStatement(actions=["s3:GetObject"], resources=[bucket.arn_for_objects(f"{names.LAKE_EVENTS_PREFIX}*")]),
            iam.PolicyStatement(
                actions=["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
                resources=[bucket.arn_for_objects(f"{names.RECS_RUNS_PREFIX}*")],
            ),
        ]
        for statement in statements:
            state_machine.add_to_role_policy(statement)

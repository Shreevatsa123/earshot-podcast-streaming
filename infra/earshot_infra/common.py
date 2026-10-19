"""CDK helpers every construct should use, so all six members build things the same way.

Owner: M6.
"""

from __future__ import annotations

from collections.abc import Mapping

from aws_cdk import Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from earshot_infra.config import SERVICES_DIR, StageConfig

#: All log groups keep logs for 7 days (CONTEXT §5).
LOG_RETENTION = logs.RetentionDays.ONE_WEEK

LAMBDA_ASSET_EXCLUDES = ["**/tests/**", "**/__pycache__/**", "**/*.pyc"]


def data_removal_policy(cfg: StageConfig) -> RemovalPolicy:
    """RETAIN in prod, DESTROY elsewhere. Only for the table and lake bucket (CONTEXT §5)."""
    return RemovalPolicy.RETAIN if cfg.retain_data else RemovalPolicy.DESTROY


def tag_stack(stack: Stack, cfg: StageConfig) -> None:
    Tags.of(stack).add("project", "earshot")
    Tags.of(stack).add("stage", cfg.stage)


def tag_owner(scope: Construct, member: str) -> None:
    """Tag everything inside ``scope`` with ``owner=<M#>`` (CONTEXT §5)."""
    Tags.of(scope).add("owner", member)


def log_group(scope: Construct, construct_id: str, *, name: str) -> logs.LogGroup:
    """A log group with 7-day retention that's deleted with its stack."""
    return logs.LogGroup(
        scope,
        construct_id,
        log_group_name=name,
        retention=LOG_RETENTION,
        removal_policy=RemovalPolicy.DESTROY,
    )


def python_function(
    scope: Construct,
    construct_id: str,
    *,
    cfg: StageConfig,
    name: str,
    handler: str,
    environment: Mapping[str, str] | None = None,
    memory_size: int = 256,
    timeout_seconds: int = 30,
    description: str | None = None,
) -> lambda_.Function:
    """Create one of the four Earshot Lambdas with the project defaults (CONTEXT §3, §4).

    - Name ``earshot-<stage>-<name>``, where ``name`` is ``api``, ``ingest``,
      ``processor`` or ``recs-writer``.
    - Python 3.12 on arm64. Code is the whole ``services/`` folder, so ``shared/`` is
      importable. No pip dependencies and no Docker bundling.
    - ``STAGE`` is always set; pass the other variables your function uses (CONTEXT §9).
    - 7-day log group.

    Example::

        fn = python_function(self, "Function", cfg=cfg, name="ingest",
                             handler="ingest.handler.main",
                             environment={"STREAM_NAME": cfg.stream_name})
    """
    function_name = cfg.function_name(name)
    logs_ = log_group(scope, f"{construct_id}Logs", name=f"/aws/lambda/{function_name}")
    return lambda_.Function(
        scope,
        construct_id,
        function_name=function_name,
        description=description,
        runtime=lambda_.Runtime.PYTHON_3_12,
        architecture=lambda_.Architecture.ARM_64,
        handler=handler,
        code=lambda_.Code.from_asset(str(SERVICES_DIR), exclude=LAMBDA_ASSET_EXCLUDES),
        memory_size=memory_size,
        timeout=Duration.seconds(timeout_seconds),
        environment={"STAGE": cfg.stage, **dict(environment or {})},
        log_group=logs_,
    )

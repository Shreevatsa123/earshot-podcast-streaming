"""Per-stage configuration: every resource name and ARN for one stage (CONTEXT §5, §9).

Owner: M6. Pure Python with no CDK imports, so scripts can use it too.
All naming patterns live in ``services/shared/names.py``. Never build a resource name by
hand in a construct; use ``cfg.<name>``.

ARN helpers exist so the pipeline stack can reference base resources **by name**
instead of through CDK props/exports (CONTEXT §5).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from shared import names  # noqa: E402  (needs SERVICES_DIR on sys.path)

PROD_STAGE = "prod"
#: Used when no AWS credentials are available: fine for `synth`, never deployable.
PLACEHOLDER_ACCOUNT = "000000000000"


@dataclass(frozen=True)
class StageConfig:
    """Everything that differs between stages (``priya``, ``prod``, …)."""

    stage: str
    account: str
    region: str = names.REGION
    alert_email: str | None = None

    def __post_init__(self) -> None:
        names.validate_stage(self.stage)
        names.validate_account(self.account)
        if self.region != names.REGION:
            raise ValueError(f"Earshot only deploys to {names.REGION} (CONTEXT §3).")

    # ---- Stage behaviour ---------------------------------------------------------------

    @property
    def is_prod(self) -> bool:
        return self.stage == PROD_STAGE

    @property
    def retain_data(self) -> bool:
        """True only in prod: the table and lake bucket survive stack deletion (CONTEXT §5)."""
        return self.is_prod

    @property
    def is_placeholder_account(self) -> bool:
        return self.account == PLACEHOLDER_ACCOUNT

    # ---- Names (CONTEXT §9) ------------------------------------------------------------

    def stack_name(self, kind: str) -> str:
        return names.stack_name(self.stage, kind)

    def function_name(self, short_name: str) -> str:
        return names.function_name(self.stage, short_name)

    @property
    def table_name(self) -> str:
        return names.table_name(self.stage)

    @property
    def lake_bucket(self) -> str:
        return names.lake_bucket(self.stage, self.account)

    @property
    def web_bucket(self) -> str:
        return names.web_bucket(self.stage, self.account)

    @property
    def stream_name(self) -> str:
        return names.stream_name(self.stage)

    @property
    def firehose_name(self) -> str:
        return names.firehose_name(self.stage)

    @property
    def glue_database(self) -> str:
        return names.glue_database(self.stage)

    @property
    def glue_table(self) -> str:
        return names.GLUE_TABLE

    @property
    def athena_workgroup(self) -> str:
        return names.athena_workgroup(self.stage)

    @property
    def qoe_topic(self) -> str:
        return names.qoe_topic(self.stage)

    @property
    def ops_topic(self) -> str:
        return names.ops_topic(self.stage)

    @property
    def processor_dlq(self) -> str:
        return names.processor_dlq(self.stage)

    @property
    def state_machine(self) -> str:
        return names.state_machine(self.stage)

    @property
    def dashboard(self) -> str:
        return names.dashboard(self.stage)

    @property
    def cognito_domain_prefix(self) -> str:
        return names.cognito_domain_prefix(self.stage, self.account)

    @property
    def allowed_genres(self) -> str:
        """Value for the ``ALLOWED_GENRES`` Lambda environment variable."""
        return ",".join(names.GENRES)

    # ---- SSM parameters (CONTEXT §9) ---------------------------------------------------

    @property
    def ssm_prefix(self) -> str:
        return names.ssm_prefix(self.stage)

    @property
    def ssm_api_url(self) -> str:
        return names.ssm_api_url(self.stage)

    @property
    def ssm_user_pool_id(self) -> str:
        return names.ssm_user_pool_id(self.stage)

    @property
    def ssm_web_client_id(self) -> str:
        return names.ssm_web_client_id(self.stage)

    @property
    def ssm_sim_client_id(self) -> str:
        return names.ssm_sim_client_id(self.stage)

    @property
    def ssm_flags(self) -> str:
        return names.ssm_flags(self.stage)

    @property
    def ssm_sim_password(self) -> str:
        return names.ssm_sim_password(self.stage)

    # ---- ARNs (reference resources in the other stack by name; CONTEXT §5) -------------

    def _arn(self, service: str, resource: str) -> str:
        return f"arn:aws:{service}:{self.region}:{self.account}:{resource}"

    @property
    def table_arn(self) -> str:
        return self._arn("dynamodb", f"table/{self.table_name}")

    @property
    def lake_bucket_arn(self) -> str:
        return f"arn:aws:s3:::{self.lake_bucket}"

    @property
    def stream_arn(self) -> str:
        return self._arn("kinesis", f"stream/{self.stream_name}")

    @property
    def firehose_arn(self) -> str:
        return self._arn("firehose", f"deliverystream/{self.firehose_name}")

    def function_arn(self, short_name: str) -> str:
        return self._arn("lambda", f"function:{self.function_name(short_name)}")

    @property
    def processor_dlq_arn(self) -> str:
        return self._arn("sqs", self.processor_dlq)

    @property
    def qoe_topic_arn(self) -> str:
        return self._arn("sns", self.qoe_topic)

    @property
    def ops_topic_arn(self) -> str:
        return self._arn("sns", self.ops_topic)

    @property
    def glue_catalog_arn(self) -> str:
        return self._arn("glue", "catalog")

    @property
    def glue_database_arn(self) -> str:
        return self._arn("glue", f"database/{self.glue_database}")

    @property
    def glue_table_arn(self) -> str:
        return self._arn("glue", f"table/{self.glue_database}/{self.glue_table}")

    def ssm_parameter_arn(self, path: str) -> str:
        """ARN of an SSM parameter; ``path`` starts with ``/`` (e.g. ``cfg.ssm_flags``)."""
        return self._arn("ssm", f"parameter{path}")

    @property
    def ssm_stage_parameters_arn(self) -> str:
        """Wildcard ARN covering every ``/earshot/<stage>/*`` parameter."""
        return self.ssm_parameter_arn(f"{self.ssm_prefix}/*")

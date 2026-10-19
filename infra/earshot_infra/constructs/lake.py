"""Glue Data Catalog table and Athena workgroup for the event lake.

Owner: M5 · Stack: base · Tracker: M5-01 · Spec: CONTEXT §9 (Glue table, lake layout)

STATUS: STUB. Creates nothing yet. The lake **bucket** itself is ``core.lake_bucket``.

Must create:
- Glue database ``cfg.glue_database`` and table ``cfg.glue_table``: Parquet, columns
  exactly as in §6, partitions ``dt``/``hour`` with **partition projection** (no
  crawlers). Use the L1 ``aws_glue.CfnDatabase`` / ``CfnTable``; the Glue L2 is a
  separate alpha package, so don't add it.
- Athena workgroup ``cfg.athena_workgroup``: results at
  ``s3://<lake>/athena-results/``, 1 GB per-query scan cutoff, enforce workgroup
  config, ``recursive_delete_option=True`` (so stack deletion works after queries ran).
- Lifecycle rule on the shared bucket:
  ``core.lake_bucket.add_lifecycle_rule(prefix="athena-results/", expiration=Duration.days(7))``.

Exposes (keep these names; ``Recs`` reads them): ``database``, ``table``, ``workgroup``.
Each is None until implemented. Pipeline code refers to them by name (``cfg.glue_*``).
"""

from __future__ import annotations

from aws_cdk import aws_athena as athena
from aws_cdk import aws_glue as glue
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class Lake(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core) -> None:
        super().__init__(scope, construct_id)
        self.database: glue.CfnDatabase | None = None
        self.table: glue.CfnTable | None = None
        self.workgroup: athena.CfnWorkGroup | None = None
        # TODO(M5-01): implement per the docstring.

"""Glue Data Catalog table and Athena workgroup for the event lake.

Owner: M5 · Stack: base · Tracker: M5-01 · Spec: CONTEXT §9 (Glue table, lake layout)

The lake **bucket** itself is ``core.lake_bucket`` (M6). This construct creates:

- Glue database ``cfg.glue_database`` and table ``cfg.glue_table``: Parquet, columns
  exactly as in §6, partitions ``dt``/``hour`` with **partition projection** (no
  crawlers, no ``MSCK REPAIR``). L1 ``CfnDatabase`` / ``CfnTable``, because the Glue L2
  is a separate alpha package.
- Athena workgroup ``cfg.athena_workgroup``: default results at
  ``s3://<lake>/athena-results/``, 1 GB per-query scan cutoff,
  ``recursive_delete_option=True`` (so stack deletion works after queries ran).
- A 7-day lifecycle rule on ``athena-results/`` in the shared lake bucket.

The workgroup does **not** enforce its configuration. Enforcing would override each
query's own output location, and the recs job (§10) writes its results under
``recs-runs/<run_id>/``. The scan cutoff applies either way.

The table is also the lake's schema: Firehose (M5-02) converts JSON to Parquet using it,
so a wrong column here means wrong files or records in ``errors/``.

Exposes (keep these names; ``Recs`` reads them): ``database``, ``table``, ``workgroup``.
Pipeline code refers to them by name (``cfg.glue_*``).
"""

from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_athena as athena
from aws_cdk import aws_glue as glue
from constructs import Construct

from earshot_infra.config import StageConfig, names
from earshot_infra.constructs.core import Core

#: Event columns in CONTEXT §6 order, as (name, Glue/Hive type).
EVENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("event_id", "string"),
    ("schema_version", "int"),
    ("user_id", "string"),
    ("session_id", "string"),
    ("show_id", "string"),
    ("episode_id", "string"),
    ("genre", "string"),
    ("event_type", "string"),
    ("position_sec", "int"),
    ("duration_sec", "int"),
    ("client_ts", "bigint"),
    ("server_ts", "bigint"),
    ("region", "string"),
    ("device", "string"),
)

#: Hive-style partitions written by Firehose's timestamp prefix (UTC arrival time).
PARTITION_KEYS: tuple[tuple[str, str], ...] = (("dt", "string"), ("hour", "string"))

#: First date the projection covers (CONTEXT §9).
PROJECTION_START = "2026-09-01"

#: Per-query scan cutoff for the workgroup (CONTEXT §9): 1 GB.
SCAN_CUTOFF_BYTES = 1024**3

ATHENA_RESULTS_RETENTION = Duration.days(7)

PARQUET_INPUT_FORMAT = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
PARQUET_OUTPUT_FORMAT = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
PARQUET_SERDE = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"


def projection_parameters(events_location: str) -> dict[str, str]:
    """Table parameters for partition projection over ``dt=YYYY-MM-DD/hour=HH/`` folders.

    Athena computes partitions from these instead of reading them from the catalog. A typo
    here doesn't fail: queries just return 0 rows. ``hour`` has 2 digits to match the
    ``!{timestamp:HH}`` prefix Firehose writes.
    """
    return {
        "classification": "parquet",
        "projection.enabled": "true",
        "projection.dt.type": "date",
        "projection.dt.format": "yyyy-MM-dd",
        "projection.dt.range": f"{PROJECTION_START},NOW",
        "projection.dt.interval": "1",
        "projection.dt.interval.unit": "DAYS",
        "projection.hour.type": "integer",
        "projection.hour.range": "0,23",
        "projection.hour.digits": "2",
        "storage.location.template": f"{events_location}dt=${{dt}}/hour=${{hour}}/",
    }


class Lake(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core) -> None:
        super().__init__(scope, construct_id)
        lake_url = f"s3://{cfg.lake_bucket}/"
        events_location = f"{lake_url}{names.LAKE_EVENTS_PREFIX}"

        database = glue.CfnDatabase(
            self,
            "Database",
            catalog_id=cfg.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=cfg.glue_database,
                description="Earshot playback event lake (CONTEXT §9)",
            ),
        )

        table = glue.CfnTable(
            self,
            "EventsTable",
            catalog_id=cfg.account,
            database_name=cfg.glue_database,
            table_input=glue.CfnTable.TableInputProperty(
                name=cfg.glue_table,
                description="Playback events, schema v1 (CONTEXT §6), written by Firehose",
                table_type="EXTERNAL_TABLE",
                parameters=projection_parameters(events_location),
                partition_keys=[glue.CfnTable.ColumnProperty(name=n, type=t) for n, t in PARTITION_KEYS],
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=[glue.CfnTable.ColumnProperty(name=n, type=t) for n, t in EVENT_COLUMNS],
                    location=events_location,
                    input_format=PARQUET_INPUT_FORMAT,
                    output_format=PARQUET_OUTPUT_FORMAT,
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library=PARQUET_SERDE,
                        parameters={"serialization.format": "1"},
                    ),
                ),
            ),
        )
        # L1 resources refer to the database by name only, so CloudFormation doesn't know
        # the order. Without this, the table can be created first and fail.
        table.add_dependency(database)

        workgroup = athena.CfnWorkGroup(
            self,
            "Workgroup",
            name=cfg.athena_workgroup,
            description="Earshot queries: analytics, recs, reconciliation (CONTEXT §9)",
            state="ENABLED",
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                bytes_scanned_cutoff_per_query=SCAN_CUTOFF_BYTES,
                enforce_work_group_configuration=False,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"{lake_url}{names.ATHENA_RESULTS_PREFIX}",
                ),
            ),
        )

        core.lake_bucket.add_lifecycle_rule(
            id="ExpireAthenaResults",
            prefix=names.ATHENA_RESULTS_PREFIX,
            expiration=ATHENA_RESULTS_RETENTION,
        )

        self.database: glue.CfnDatabase | None = database
        self.table: glue.CfnTable | None = table
        self.workgroup: athena.CfnWorkGroup | None = workgroup

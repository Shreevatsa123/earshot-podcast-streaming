"""Amazon Data Firehose: Kinesis -> Parquet files in the lake bucket.

Owner: M5 · Stack: **pipeline** (billed per GB) · Tracker: M5-02 · Spec: CONTEXT §9 "Firehose", lake layout

STATUS: STUB. Creates nothing yet.

Must create:
- Delivery stream ``cfg.firehose_name`` (L1 ``aws_kinesisfirehose.CfnDeliveryStream``):
  - source: ``stream`` (Kinesis stream as source)
  - destination: the lake bucket **by ARN**, ``cfg.lake_bucket_arn`` (it lives in base)
  - prefix ``events/dt=!{timestamp:yyyy-MM-dd}/hour=!{timestamp:HH}/``
  - error prefix ``errors/!{firehose:error-output-type}/dt=!{timestamp:yyyy-MM-dd}/``
  - buffering 64 MiB / 60 s; Parquet conversion using the Glue table
    ``cfg.glue_database`` / ``cfg.glue_table``
  - CloudWatch error logging to ``common.log_group(...)`` (7 days)
- A role for Firehose: read on the stream, write on the lake bucket, ``glue:GetTable*`` on
  ``cfg.glue_catalog_arn`` / ``cfg.glue_database_arn`` / ``cfg.glue_table_arn``.

Cost gotcha: don't enable *dynamic partitioning*. The timestamp prefixes above are free;
dynamic partitioning is billed extra.

Inputs: ``stream`` from ``Stream`` (None until M3-03; skip if so).
Exposes: nothing.
"""

from __future__ import annotations

from aws_cdk import aws_kinesis as kinesis
from constructs import Construct

from earshot_infra.config import StageConfig


class Firehose(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: StageConfig,
        stream: kinesis.IStream | None,
    ) -> None:
        super().__init__(scope, construct_id)
        # TODO(M5-02): implement per the docstring.

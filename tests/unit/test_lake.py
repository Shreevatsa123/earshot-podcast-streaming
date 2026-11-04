"""M5-01: Glue database, events table and Athena workgroup (CONTEXT §6, §9).

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

import json
from pathlib import Path

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs.lake import EVENT_COLUMNS  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402

ACCOUNT = "123456789012"
# A hyphenated stage checks that the Glue database name uses underscores (§9).
STAGE = "m5-dev"
LAKE = f"s3://earshot-{STAGE}-lake-{ACCOUNT}"
CONTEXT_MD = Path(__file__).resolve().parents[2] / "CONTEXT.md"


def synth(stage: str) -> tuple[BaseStack, Template]:
    app = cdk.App()
    cfg = StageConfig(stage=stage, account=ACCOUNT)
    stack = BaseStack(
        app, cfg.stack_name("base"), cfg=cfg, env=cdk.Environment(account=ACCOUNT, region=cfg.region)
    )
    return stack, Template.from_stack(stack)


@pytest.fixture(scope="module")
def dev() -> tuple[BaseStack, Template]:
    return synth(STAGE)


def only(template: Template, resource_type: str) -> tuple[str, dict]:
    """The single resource of ``resource_type`` as (logical id, resource)."""
    found = template.find_resources(resource_type)
    assert len(found) == 1, f"expected one {resource_type}, found {len(found)}"
    return next(iter(found.items()))


def contract_example_event() -> dict:
    """The example event in CONTEXT §6, so the table can't drift from the contract."""
    section = CONTEXT_MD.read_text(encoding="utf-8").split("## 6.", 1)[1].split("## 7.", 1)[0]
    return json.loads(section.split("```json", 1)[1].split("```", 1)[0])


def test_columns_match_the_contract_example_event():
    example = contract_example_event()
    assert [name for name, _ in EVENT_COLUMNS] == list(example)
    for name, glue_type in EVENT_COLUMNS:
        value = example[name]
        if isinstance(value, str):
            assert glue_type == "string", name
        elif value > 2**31 - 1:  # epoch milliseconds don't fit in a 32-bit int
            assert glue_type == "bigint", name
        else:
            assert glue_type == "int", name


def test_glue_database_name_uses_underscores(dev):
    _, template = dev
    _, database = only(template, "AWS::Glue::Database")
    assert database["Properties"]["CatalogId"] == ACCOUNT
    assert database["Properties"]["DatabaseInput"]["Name"] == "earshot_m5_dev"


def test_events_table_schema_and_storage(dev):
    _, template = dev
    _, table = only(template, "AWS::Glue::Table")
    props = table["Properties"]
    assert props["DatabaseName"] == "earshot_m5_dev"
    table_input = props["TableInput"]
    assert table_input["Name"] == "events"
    assert table_input["TableType"] == "EXTERNAL_TABLE"
    assert table_input["PartitionKeys"] == [
        {"Name": "dt", "Type": "string"},
        {"Name": "hour", "Type": "string"},
    ]
    storage = table_input["StorageDescriptor"]
    assert storage["Columns"] == [{"Name": n, "Type": t} for n, t in EVENT_COLUMNS]
    assert storage["Location"] == f"{LAKE}/events/"
    assert storage["InputFormat"].endswith("MapredParquetInputFormat")
    assert storage["OutputFormat"].endswith("MapredParquetOutputFormat")
    assert storage["SerdeInfo"]["SerializationLibrary"].endswith("ParquetHiveSerDe")


def test_partition_projection_matches_firehose_prefixes(dev):
    """Projection typos don't error in Athena; they return 0 rows. Pin every value."""
    _, template = dev
    _, table = only(template, "AWS::Glue::Table")
    assert table["Properties"]["TableInput"]["Parameters"] == {
        "classification": "parquet",
        "projection.enabled": "true",
        "projection.dt.type": "date",
        "projection.dt.format": "yyyy-MM-dd",
        "projection.dt.range": "2026-09-01,NOW",
        "projection.dt.interval": "1",
        "projection.dt.interval.unit": "DAYS",
        "projection.hour.type": "integer",
        "projection.hour.range": "0,23",
        "projection.hour.digits": "2",
        "storage.location.template": f"{LAKE}/events/dt=${{dt}}/hour=${{hour}}/",
    }


def test_table_is_created_after_its_database(dev):
    _, template = dev
    database_id, _ = only(template, "AWS::Glue::Database")
    _, table = only(template, "AWS::Glue::Table")
    assert database_id in table.get("DependsOn", [])


def test_prod_uses_prod_names():
    _, template = synth("prod")
    _, database = only(template, "AWS::Glue::Database")
    assert database["Properties"]["DatabaseInput"]["Name"] == "earshot_prod"

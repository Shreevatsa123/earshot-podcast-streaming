"""M5-05: the recs job's CDK construct: the writer function (CONTEXT §10 "Recommendations").

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

from typing import Any

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs import recs  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402
from earshot_infra.stacks.pipeline_stack import PipelineStack  # noqa: E402

ACCOUNT = "123456789012"
STAGE = "m5-dev"
LAKE = f"earshot-{STAGE}-lake-{ACCOUNT}"


@pytest.fixture(scope="module")
def stacks() -> tuple[BaseStack, Template]:
    app = cdk.App()
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    env = cdk.Environment(account=ACCOUNT, region=cfg.region)
    base = BaseStack(app, cfg.stack_name("base"), cfg=cfg, env=env)
    PipelineStack(app, cfg.stack_name("pipeline"), cfg=cfg, env=env)  # both before any synth
    return base, Template.from_stack(base)


def only(template: Template, resource_type: str, props: dict[str, Any]) -> tuple[str, dict]:
    found = template.find_resources(resource_type, {"Properties": props})
    assert len(found) == 1, f"expected one {resource_type} with {props}"
    return next(iter(found.items()))


def role_statements(template: Template, role_id: str) -> list[dict[str, Any]]:
    return [
        statement
        for policy in template.find_resources("AWS::IAM::Policy").values()
        if {"Ref": role_id} in policy["Properties"]["Roles"]
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]


def actions(statement: dict[str, Any]) -> list[str]:
    action = statement["Action"]
    return [action] if isinstance(action, str) else action


# ---- The writer ---------------------------------------------------------------------------


def test_writer_function(stacks):
    _, template = stacks
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": f"earshot-{STAGE}-recs-writer",
            "Handler": "recs_writer.handler.main",
            "Runtime": "python3.12",
            "Timeout": 120,
            "Environment": {"Variables": {"STAGE": STAGE, "TABLE_NAME": f"earshot-{STAGE}-main", "LAKE_BUCKET": LAKE}},
        },
    )


def test_writer_may_write_the_table_and_read_only_recs_runs(stacks):
    _, template = stacks
    _, function = only(template, "AWS::Lambda::Function", {"FunctionName": f"earshot-{STAGE}-recs-writer"})
    statements = role_statements(template, function["Properties"]["Role"]["Fn::GetAtt"][0])
    s3 = [s for s in statements if any(a.startswith("s3:") for a in actions(s))]
    assert len(s3) == 1 and actions(s3[0]) == ["s3:GetObject"]
    assert s3[0]["Resource"]["Fn::Join"][1][1] == "/recs-runs/*"  # no listing, nothing under events/
    dynamodb = [s for s in statements if any(a.startswith("dynamodb:") for a in actions(s))]
    assert len(dynamodb) == 1 and {"dynamodb:BatchWriteItem", "dynamodb:PutItem"} <= set(actions(dynamodb[0]))


def test_recs_exposes_its_writer(stacks):
    base, _ = stacks
    construct = base.node.find_child("Recs")
    assert isinstance(construct, recs.Recs)
    assert construct.function is not None

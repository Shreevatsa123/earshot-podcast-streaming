"""M5-05: the recs job's CDK construct (CONTEXT §10 "Recommendations").

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

import json
from pathlib import Path
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
ATHENA_DIR = Path(__file__).resolve().parents[2] / "athena"


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


def definition(template: Template) -> dict[str, Any]:
    """The state machine's definition as JSON, with CloudFormation references as "<TOKEN>"."""
    _, machine = only(template, "AWS::StepFunctions::StateMachine", {"StateMachineName": f"earshot-{STAGE}-recs"})
    parts = machine["Properties"]["DefinitionString"]["Fn::Join"][1]
    return json.loads("".join(p if isinstance(p, str) else "<TOKEN>" for p in parts))


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


# ---- The state machine --------------------------------------------------------------------


def test_state_machine_is_a_standard_jsonata_job_with_a_timeout(stacks):
    _, template = stacks
    only(
        template,
        "AWS::StepFunctions::StateMachine",
        {"StateMachineName": f"earshot-{STAGE}-recs", "StateMachineType": "STANDARD"},
    )
    flow = definition(template)
    assert flow["QueryLanguage"] == "JSONata"
    assert flow["TimeoutSeconds"] == 900
    assert flow["StartAt"] == "Prepare"
    assert (flow["States"]["Prepare"]["Next"], flow["States"]["Queries"]["Next"]) == ("Queries", "Write")
    assert flow["States"]["Write"]["End"] is True


def test_prepare_sets_the_run_id_and_the_window_end(stacks):
    _, template = stacks
    assert definition(template)["States"]["Prepare"]["Assign"] == {
        "run_id": "{% $states.context.Execution.Name %}",
        "end_ms": "{% $exists($states.input.as_of) ? $toMillis($states.input.as_of)"
        " : $toMillis($states.context.Execution.StartTime) %}",
    }


def athena_branches(template: Template) -> dict[str, dict[str, Any]]:
    branches = definition(template)["States"]["Queries"]["Branches"]
    return {name: state for branch in branches for name, state in branch["States"].items()}


@pytest.mark.parametrize(("state", "query", "days"), [("RecsQuery", "recs", 30), ("PopularQuery", "popular", 7)])
def test_each_query_runs_its_file_in_the_workgroup_with_its_window(stacks, state, query, days):
    _, template = stacks
    task = athena_branches(template)[state]
    assert task["Resource"] == "arn:<TOKEN>:states:::athena:startQueryExecution.sync"  # waits for the result
    args = task["Arguments"]
    assert args["QueryString"] == (ATHENA_DIR / f"{query}.sql").read_text(encoding="utf-8")
    assert args["WorkGroup"] == f"earshot-{STAGE}"
    assert args["QueryExecutionContext"] == {"Database": "earshot_m5_dev"}
    # The whole value is one JSONata expression, so the per-run folder is evaluated.
    assert args["ResultConfiguration"] == {
        "OutputLocation": f"{{% 's3://{LAKE}/recs-runs/' & $run_id & '/' %}}"
    }
    assert args["ExecutionParameters"] == recs.window_parameters(days)
    assert task["Retry"] == [recs.ATHENA_RETRY]
    assert task["Output"] == "{% $states.result.QueryExecution.ResultConfiguration.OutputLocation %}"


def test_window_parameters_quote_dates_but_not_numbers():
    """Athena pastes these into the SQL: '2026-11-01' must be quoted, 1794614400000 must not."""
    dt_from, dt_to, start_ms, end_ms = recs.window_parameters(7)
    assert dt_from == "{% \"'\" & $fromMillis($end_ms - 604800000, '[Y0001]-[M01]-[D01]') & \"'\" %}"
    assert dt_to == "{% \"'\" & $fromMillis($end_ms + 86400000, '[Y0001]-[M01]-[D01]') & \"'\" %}"
    assert start_ms == "{% $string($end_ms - 604800000) %}"
    assert end_ms == "{% $string($end_ms) %}"
    assert recs.window_parameters(30)[2] == "{% $string($end_ms - 2592000000) %}"


def test_query_parameters_match_what_the_sql_files_expect():
    """Each file documents 4 positional parameters; the job passes exactly 4."""
    for query in ("recs", "popular"):
        sql = (ATHENA_DIR / f"{query}.sql").read_text(encoding="utf-8")
        code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        assert code.count("?") == len(recs.window_parameters(1)) == 4


def test_writer_gets_the_run_id_and_both_result_paths(stacks):
    _, template = stacks
    write = definition(template)["States"]["Write"]
    assert write["Arguments"]["Payload"] == {
        "run_id": "{% $run_id %}",
        "recs_csv": "{% $states.input[0] %}",  # branch order: recs, then popular
        "popular_csv": "{% $states.input[1] %}",
    }
    assert write["Output"] == "{% $states.result.Payload %}"  # {run_id, users_written, popular_count}
    branches = definition(template)["States"]["Queries"]["Branches"]
    assert [list(b["States"]) for b in branches] == [["RecsQuery"], ["PopularQuery"]]


def test_state_machine_role_is_scoped_to_this_stage(stacks):
    """CDK's own Athena task would grant every S3 object, bucket creation and Glue writes."""
    _, template = stacks
    _, machine = only(template, "AWS::StepFunctions::StateMachine", {"StateMachineName": f"earshot-{STAGE}-recs"})
    statements = role_statements(template, machine["Properties"]["RoleArn"]["Fn::GetAtt"][0])
    assert all(s["Resource"] != "*" for s in statements)
    granted = {a for s in statements for a in actions(s)}
    assert not {a for a in granted if a.startswith("glue:") and not a.startswith("glue:Get")}
    assert "s3:CreateBucket" not in granted and "s3:DeleteObject" not in granted
    rendered = json.dumps(statements)
    assert f"workgroup/earshot-{STAGE}" in rendered
    assert "table/earshot_m5_dev/events" in rendered
    puts = [s for s in statements if "s3:PutObject" in actions(s)]
    assert len(puts) == 1 and puts[0]["Resource"]["Fn::Join"][1][1] == "/recs-runs/*"
    reads = [s for s in statements if actions(s) == ["s3:GetObject"]]
    assert len(reads) == 1 and reads[0]["Resource"]["Fn::Join"][1][1] == "/events/*"
    invokes = [s for s in statements if "lambda:InvokeFunction" in actions(s)]
    assert len(invokes) == 1


def test_recs_exposes_its_resources(stacks):
    base, _ = stacks
    construct = base.node.find_child("Recs")
    assert isinstance(construct, recs.Recs)
    assert construct.function is not None and construct.state_machine is not None

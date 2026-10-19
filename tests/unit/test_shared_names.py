import pytest

from shared import names

ACCOUNT = "123456789012"


def test_names_match_context_section_9():
    assert names.table_name("priya") == "earshot-priya-main"
    assert names.lake_bucket("priya", ACCOUNT) == "earshot-priya-lake-123456789012"
    assert names.web_bucket("priya", ACCOUNT) == "earshot-priya-web-123456789012"
    assert names.stream_name("priya") == "earshot-priya-events"
    assert names.firehose_name("priya") == "earshot-priya-events-to-s3"
    assert names.athena_workgroup("priya") == "earshot-priya"
    assert names.qoe_topic("priya") == "earshot-priya-qoe-alerts"
    assert names.ops_topic("priya") == "earshot-priya-ops-alerts"
    assert names.processor_dlq("priya") == "earshot-priya-processor-dlq"
    assert names.state_machine("priya") == "earshot-priya-recs"
    assert names.cognito_domain_prefix("priya", ACCOUNT) == "earshot-priya-789012"
    assert names.function_name("priya", "recs-writer") == "earshot-priya-recs-writer"
    assert names.stack_name("priya", "pipeline") == "earshot-priya-pipeline"


def test_glue_database_replaces_hyphens():
    assert names.glue_database("priya") == "earshot_priya"
    assert names.glue_database("team-a") == "earshot_team_a"


def test_ssm_parameter_paths():
    assert names.ssm_api_url("prod") == "/earshot/prod/api/url"
    assert names.ssm_user_pool_id("prod") == "/earshot/prod/cognito/user-pool-id"
    assert names.ssm_web_client_id("prod") == "/earshot/prod/cognito/web-client-id"
    assert names.ssm_sim_client_id("prod") == "/earshot/prod/cognito/sim-client-id"
    assert names.ssm_flags("prod") == "/earshot/prod/flags"
    assert names.ssm_sim_password("prod") == "/earshot/prod/sim/password"
    assert names.ssm_podcastindex_key("prod") == "/earshot/prod/podcastindex/key"
    assert names.ssm_podcastindex_secret("prod") == "/earshot/prod/podcastindex/secret"


def test_genres_are_the_fixed_eight():
    assert list(names.GENRES) == [
        "true-crime", "comedy", "news", "technology", "business", "science", "sports", "history",
    ]


@pytest.mark.parametrize("stage", ["priya", "prod", "m6", "team-a", "a1b2c3d4e5f6g7h8"])
def test_valid_stages(stage):
    assert names.validate_stage(stage) == stage


@pytest.mark.parametrize(
    "stage", ["", "p", "Priya", "1abc", "team_a", "team-", "team--a", "a" * 17, "pri ya", None]
)
def test_invalid_stages(stage):
    with pytest.raises(ValueError):
        names.validate_stage(stage)


@pytest.mark.parametrize("account", ["12345678901", "1234567890123", "abcdefghijkl", ""])
def test_invalid_accounts(account):
    with pytest.raises(ValueError):
        names.lake_bucket("priya", account)


def test_unknown_function_and_stack_rejected():
    with pytest.raises(ValueError):
        names.function_name("priya", "worker")
    with pytest.raises(ValueError):
        names.stack_name("priya", "data")


def test_required_env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "earshot-priya-main")
    assert names.required_env("TABLE_NAME") == "earshot-priya-main"
    monkeypatch.delenv("TABLE_NAME")
    with pytest.raises(RuntimeError, match="TABLE_NAME"):
        names.required_env("TABLE_NAME")

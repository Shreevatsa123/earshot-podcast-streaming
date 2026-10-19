import pytest

from earshot_infra.config import PLACEHOLDER_ACCOUNT, StageConfig

ACCOUNT = "123456789012"


def test_stage_config_names_and_arns():
    cfg = StageConfig(stage="priya", account=ACCOUNT)
    assert cfg.table_name == "earshot-priya-main"
    assert cfg.stream_arn == f"arn:aws:kinesis:us-east-1:{ACCOUNT}:stream/earshot-priya-events"
    assert cfg.lake_bucket_arn == f"arn:aws:s3:::earshot-priya-lake-{ACCOUNT}"
    assert cfg.function_arn("processor") == (
        f"arn:aws:lambda:us-east-1:{ACCOUNT}:function:earshot-priya-processor"
    )
    assert cfg.processor_dlq_arn == f"arn:aws:sqs:us-east-1:{ACCOUNT}:earshot-priya-processor-dlq"
    assert cfg.glue_table_arn == f"arn:aws:glue:us-east-1:{ACCOUNT}:table/earshot_priya/events"
    assert cfg.ssm_stage_parameters_arn == f"arn:aws:ssm:us-east-1:{ACCOUNT}:parameter/earshot/priya/*"
    assert cfg.allowed_genres.split(",")[0] == "true-crime"


def test_only_prod_retains_data():
    assert StageConfig(stage="prod", account=ACCOUNT).retain_data is True
    assert StageConfig(stage="priya", account=ACCOUNT).retain_data is False


def test_rejects_bad_stage_account_and_region():
    with pytest.raises(ValueError):
        StageConfig(stage="Priya", account=ACCOUNT)
    with pytest.raises(ValueError):
        StageConfig(stage="priya", account="123")
    with pytest.raises(ValueError):
        StageConfig(stage="priya", account=ACCOUNT, region="eu-west-1")


def test_placeholder_account_is_flagged():
    assert StageConfig(stage="priya", account=PLACEHOLDER_ACCOUNT).is_placeholder_account

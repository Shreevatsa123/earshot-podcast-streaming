"""M1-04: web bucket, CloudFront with OAC, SPA routing and the config.json deployment (CONTEXT §9).

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

import json
from pathlib import Path

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Match, Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.constructs import web as web_module  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402

ACCOUNT = "123456789012"
STAGE = "m1-dev"


def synth(monkeypatch: pytest.MonkeyPatch, dist: Path) -> Template:
    monkeypatch.setattr(web_module, "WEB_DIST_DIR", dist)
    app = cdk.App()
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    stack = BaseStack(
        app, cfg.stack_name("base"), cfg=cfg, env=cdk.Environment(account=ACCOUNT, region=cfg.region)
    )
    return Template.from_stack(stack)


@pytest.fixture
def built_app(tmp_path: Path) -> Path:
    """A fake ``web/dist`` with an index page and the local config.json the build copies in."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    (dist / "assets" / "index.js").write_text("console.log('earshot')")
    (dist / "config.json").write_text('{"stage":"local"}')
    return dist


@pytest.fixture
def template(monkeypatch: pytest.MonkeyPatch, built_app: Path) -> Template:
    return synth(monkeypatch, built_app)


def deployment(template: Template) -> dict:
    found = template.find_resources("Custom::CDKBucketDeployment")
    assert len(found) == 1, f"expected one BucketDeployment, found {len(found)}"
    return next(iter(found.values()))["Properties"]


def test_private_bucket_named_per_stage(template: Template) -> None:
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": f"earshot-{STAGE}-web-{ACCOUNT}",
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )
    template.has_resource(
        "AWS::S3::Bucket",
        {"Properties": {"BucketName": f"earshot-{STAGE}-web-{ACCOUNT}"}, "DeletionPolicy": "Delete"},
    )


def test_cloudfront_reads_the_bucket_through_oac_only(template: Template) -> None:
    template.resource_count_is("AWS::CloudFront::OriginAccessControl", 1)
    template.resource_count_is("AWS::CloudFront::CloudFrontOriginAccessIdentity", 0)
    policies = template.find_resources("AWS::S3::BucketPolicy")
    text = json.dumps(policies)
    assert "cloudfront.amazonaws.com" in text and "AWS:SourceArn" in text


def test_distribution_serves_the_spa_over_https(template: Template) -> None:
    template.resource_count_is("AWS::CloudFront::Distribution", 1)
    template.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": Match.object_like(
                {
                    "DefaultRootObject": "index.html",
                    "PriceClass": "PriceClass_100",
                    "DefaultCacheBehavior": Match.object_like({"ViewerProtocolPolicy": "redirect-to-https"}),
                    "CustomErrorResponses": [
                        {"ErrorCode": 403, "ResponseCode": 200, "ResponsePagePath": "/index.html", "ErrorCachingMinTTL": 0},
                        {"ErrorCode": 404, "ResponseCode": 200, "ResponsePagePath": "/index.html", "ErrorCachingMinTTL": 0},
                    ],
                }
            )
        },
    )


def test_deploys_app_and_config_then_invalidates(template: Template) -> None:
    props = deployment(template)
    assert len(props["SourceBucketNames"]) == 2  # web/dist + the generated config.json
    assert props["DistributionPaths"] == ["/*"]
    assert "DistributionId" in props


def test_config_json_has_every_field_with_the_stage_values(
    monkeypatch: pytest.MonkeyPatch, built_app: Path, tmp_path: Path
) -> None:
    """Synthesizes to disk and reads the generated config.json. CloudFormation values are
    placeholders in the file, filled in at deploy time from ``SourceMarkers``."""
    monkeypatch.setattr(web_module, "WEB_DIST_DIR", built_app)
    app = cdk.App(outdir=str(tmp_path / "cdk.out"))
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    stack = BaseStack(
        app, cfg.stack_name("base"), cfg=cfg, env=cdk.Environment(account=ACCOUNT, region=cfg.region)
    )
    app.synth()
    files = list((tmp_path / "cdk.out").glob("asset.*/config.json"))
    generated = [json.loads(f.read_text()) for f in files if "apiUrl" in f.read_text()]
    assert len(generated) == 1, "expected exactly one generated config.json"
    config = generated[0]

    assert set(config) == {"apiUrl", "region", "userPoolId", "webClientId", "cognitoDomain", "stage"}
    assert config["region"] == "us-east-1"
    assert config["stage"] == STAGE
    assert config["cognitoDomain"].startswith("https://")
    assert config["cognitoDomain"].endswith(".auth.us-east-1.amazoncognito.com")
    for field in ("apiUrl", "userPoolId", "webClientId"):
        assert config[field].startswith("<<marker:"), f"{field} should be filled in at deploy time"

    markers = json.dumps(deployment(Template.from_stack(stack))["SourceMarkers"])
    for ref in ("ApiEndpoint", "UserPool", "WebClient", "Domain"):
        assert ref in markers, f"{ref} missing from the deploy-time values"


def test_the_local_config_json_is_left_out_of_the_upload(
    monkeypatch: pytest.MonkeyPatch, built_app: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr(web_module, "WEB_DIST_DIR", built_app)
    app = cdk.App(outdir=str(tmp_path / "cdk.out"))
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    BaseStack(app, cfg.stack_name("base"), cfg=cfg, env=cdk.Environment(account=ACCOUNT, region=cfg.region))
    app.synth()
    [app_asset] = [d for d in (tmp_path / "cdk.out").glob("asset.*") if (d / "index.html").exists()]
    assert (app_asset / "assets" / "index.js").exists()
    assert not (app_asset / "config.json").exists()


def test_without_a_build_only_config_json_is_deployed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    props = deployment(synth(monkeypatch, tmp_path / "missing-dist"))
    assert len(props["SourceBucketNames"]) == 1


def test_web_url_is_the_cloudfront_domain(template: Template) -> None:
    [client] = [
        r["Properties"]
        for r in template.find_resources("AWS::Cognito::UserPoolClient").values()
        if r["Properties"]["ClientName"] == "web"
    ]
    url = client["CallbackURLs"][0]
    assert url["Fn::Join"][1][0] == "https://"
    assert "DomainName" in json.dumps(url["Fn::Join"][1][1])

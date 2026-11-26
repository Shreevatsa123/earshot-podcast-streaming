"""M2-04: HTTP API, JWT authorizer, routes, CORS, throttling and the API Lambda (CONTEXT §7.1, §7.3).

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402

ACCOUNT = "123456789012"
STAGE = "m2-dev"
ROUTES = {
    "GET /health",
    "GET /genres",
    "GET /shows",
    "GET /shows/{showId}",
    "GET /progress/{episodeId}",
    "GET /trending",
    "GET /home",
    "POST /events",
}


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    stack = BaseStack(
        app, cfg.stack_name("base"), cfg=cfg, env=cdk.Environment(account=ACCOUNT, region=cfg.region)
    )
    return Template.from_stack(stack)


def props(template: Template, resource_type: str) -> list[dict]:
    return [r["Properties"] for r in template.find_resources(resource_type).values()]


def test_http_api_with_cors(template: Template) -> None:
    [api] = props(template, "AWS::ApiGatewayV2::Api")
    assert api["ProtocolType"] == "HTTP"
    cors = api["CorsConfiguration"]
    assert cors["AllowOrigins"] == ["http://localhost:5173"]  # + the CloudFront URL once M1-04 exists
    assert set(cors["AllowMethods"]) == {"GET", "POST", "OPTIONS"}
    assert set(cors["AllowHeaders"]) == {"authorization", "content-type", "x-earshot-sim-user"}


def test_jwt_authorizer_accepts_both_app_clients(template: Template) -> None:
    [authorizer] = props(template, "AWS::ApiGatewayV2::Authorizer")
    assert authorizer["AuthorizerType"] == "JWT"
    assert len(authorizer["JwtConfiguration"]["Audience"]) == 2
    assert "cognito-idp" in str(authorizer["JwtConfiguration"]["Issuer"])


def test_routes_need_a_token_except_health(template: Template) -> None:
    routes = {r["RouteKey"]: r for r in props(template, "AWS::ApiGatewayV2::Route")}
    assert set(routes) == ROUTES
    for key, route in routes.items():
        assert route["AuthorizationType"] == ("NONE" if key == "GET /health" else "JWT"), key
        assert not route.get("AuthorizationScopes"), f"{key}: web and sim tokens carry different scopes"


def test_default_stage_is_throttled(template: Template) -> None:
    [stage] = props(template, "AWS::ApiGatewayV2::Stage")
    assert stage["StageName"] == "$default" and stage["AutoDeploy"] is True
    assert stage["DefaultRouteSettings"]["ThrottlingRateLimit"] == 500
    assert stage["DefaultRouteSettings"]["ThrottlingBurstLimit"] == 1000


def test_api_function_and_url_parameter(template: Template) -> None:
    functions = [f for f in props(template, "AWS::Lambda::Function") if f.get("FunctionName") == f"earshot-{STAGE}-api"]
    assert len(functions) == 1
    assert functions[0]["MemorySize"] == 512
    assert set(functions[0]["Environment"]["Variables"]) == {"STAGE", "TABLE_NAME", "FLAGS_PARAM", "ALLOWED_GENRES"}
    names = {p["Name"] for p in props(template, "AWS::SSM::Parameter")}
    assert f"/earshot/{STAGE}/api/url" in names

"""M1-02: Cognito user pool, groups, app clients, domain and SSM params (CONTEXT §9, §7.2).

Skipped when aws-cdk-lib isn't installed (run ``make install``).
"""

import pytest

cdk = pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")

from aws_cdk.assertions import Match, Template  # noqa: E402

from earshot_infra.config import StageConfig  # noqa: E402
from earshot_infra.stacks.base_stack import BaseStack  # noqa: E402

ACCOUNT = "123456789012"
STAGE = "m1-dev"


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    cfg = StageConfig(stage=STAGE, account=ACCOUNT)
    stack = BaseStack(
        app, cfg.stack_name("base"), cfg=cfg, env=cdk.Environment(account=ACCOUNT, region=cfg.region)
    )
    return Template.from_stack(stack)


def client(template: Template, name: str) -> dict:
    found = template.find_resources(
        "AWS::Cognito::UserPoolClient", {"Properties": {"ClientName": name}}
    )
    assert len(found) == 1, f"expected one {name!r} client, found {len(found)}"
    return next(iter(found.values()))["Properties"]


def test_user_pool_email_sign_in_self_sign_up_essentials(template: Template) -> None:
    template.resource_count_is("AWS::Cognito::UserPool", 1)
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UserPoolName": f"earshot-{STAGE}-users",
            "UserPoolTier": "ESSENTIALS",
            "UsernameAttributes": ["email"],
            "AutoVerifiedAttributes": ["email"],
            "AdminCreateUserConfig": {"AllowAdminCreateUserOnly": False},
        },
    )
    template.has_resource("AWS::Cognito::UserPool", {"DeletionPolicy": "Delete"})


def test_listeners_and_simulator_groups(template: Template) -> None:
    groups = template.find_resources("AWS::Cognito::UserPoolGroup")
    assert sorted(g["Properties"]["GroupName"] for g in groups.values()) == ["listeners", "simulator"]


def test_web_client_is_code_with_pkce_and_no_secret(template: Template) -> None:
    template.resource_count_is("AWS::Cognito::UserPoolClient", 2)
    web = client(template, "web")
    assert web["GenerateSecret"] is False
    assert web["AllowedOAuthFlows"] == ["code"]
    assert web["AllowedOAuthFlowsUserPoolClient"] is True
    assert "openid" in web["AllowedOAuthScopes"]
    assert web["SupportedIdentityProviders"] == ["COGNITO"]
    # Web construct isn't implemented yet (M1-04), so only localhost is registered.
    assert web["CallbackURLs"] == ["http://localhost:5173"]
    assert web["LogoutURLs"] == ["http://localhost:5173"]
    # No password flow from the browser: login happens on the managed login pages.
    assert web["ExplicitAuthFlows"] == ["ALLOW_REFRESH_TOKEN_AUTH"]


def test_sim_client_allows_password_and_refresh_auth(template: Template) -> None:
    sim = client(template, "sim")
    assert sim["GenerateSecret"] is False
    assert set(sim["ExplicitAuthFlows"]) >= {"ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"}
    assert not sim.get("AllowedOAuthFlows")


def test_managed_login_domain_and_style(template: Template) -> None:
    template.has_resource_properties(
        "AWS::Cognito::UserPoolDomain",
        {"Domain": f"earshot-{STAGE}-{ACCOUNT[-6:]}", "ManagedLoginVersion": 2},
    )
    template.has_resource_properties(
        "AWS::Cognito::ManagedLoginBranding",
        {"UseCognitoProvidedValues": True, "ClientId": Match.any_value()},
    )


def test_ssm_parameters(template: Template) -> None:
    names = {
        p["Properties"]["Name"]
        for p in template.find_resources("AWS::SSM::Parameter").values()
    }
    assert {
        f"/earshot/{STAGE}/cognito/user-pool-id",
        f"/earshot/{STAGE}/cognito/web-client-id",
        f"/earshot/{STAGE}/cognito/sim-client-id",
    } <= names

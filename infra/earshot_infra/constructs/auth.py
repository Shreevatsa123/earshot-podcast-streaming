"""Cognito user pool and app clients.

Owner: M1 · Stack: base · Tracker: M1-02 (M1-03 for the sim-bot script) · Spec: CONTEXT §9 "Cognito", §7.2

Creates:
- User pool: email sign-in, self sign-up, Essentials feature plan (free up to 10k MAU;
  managed login needs Essentials, the Lite plan only has the classic hosted UI).
  Groups ``listeners`` and ``simulator``.
- App client ``web``: no secret, authorization code + PKCE, managed login. Callback and
  logout URLs are ``web_url`` and ``http://localhost:5173``.
- App client ``sim``: no secret, ``USER_PASSWORD_AUTH`` (plus refresh), no OAuth.
- Managed login domain with prefix ``cfg.cognito_domain_prefix``, and the default
  managed login style for the web client (without a style the login page shows an error).
- SSM String parameters ``cfg.ssm_user_pool_id``, ``cfg.ssm_web_client_id`` and
  ``cfg.ssm_sim_client_id``.

Nothing adds new users to ``listeners`` automatically. Only ``simulator`` membership
matters to the API (§7.2); everyone else is treated as a listener.

Inputs:
- ``web_url``: CloudFront URL from ``Web`` (None until M1's web construct exists; then
  only the localhost URLs are registered).

Exposes (keep these names; ``Api`` and ``Web.publish`` read them):
- ``user_pool``, ``web_client``, ``sim_client``, ``domain``.
"""

from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from earshot_infra.config import StageConfig

LOCAL_DEV_URL = "http://localhost:5173"
GROUPS = ("listeners", "simulator")


class Auth(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, cfg: StageConfig, web_url: str | None
    ) -> None:
        super().__init__(scope, construct_id)

        pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{cfg.prefix}-users",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            sign_in_aliases=cognito.SignInAliases(email=True),
            sign_in_case_sensitive=False,
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # §5: DESTROY everywhere except the prod table and lake bucket.
            removal_policy=RemovalPolicy.DESTROY,
        )

        for group in GROUPS:
            cognito.CfnUserPoolGroup(
                self, f"Group-{group}", user_pool_id=pool.user_pool_id, group_name=group
            )

        app_urls = [url for url in (web_url, LOCAL_DEV_URL) if url]
        web_client = pool.add_client(
            "WebClient",
            user_pool_client_name="web",
            generate_secret=False,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=app_urls,
                logout_urls=app_urls,
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            prevent_user_existence_errors=True,
        )
        # The browser signs in on the managed login pages, so its only direct flow is token
        # refresh. CDK has no "refresh only" option, and leaving the list empty gives Cognito's
        # defaults (which include password-style flows), so set it on the CloudFormation resource.
        web_cfn = web_client.node.default_child
        assert isinstance(web_cfn, cognito.CfnUserPoolClient)
        web_cfn.explicit_auth_flows = ["ALLOW_REFRESH_TOKEN_AUTH"]

        sim_client = pool.add_client(
            "SimClient",
            user_pool_client_name="sim",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True),
            disable_o_auth=True,
            prevent_user_existence_errors=True,
        )

        domain = pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=cfg.cognito_domain_prefix),
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
        )

        branding = cognito.CfnManagedLoginBranding(
            self,
            "WebLoginStyle",
            user_pool_id=pool.user_pool_id,
            client_id=web_client.user_pool_client_id,
            use_cognito_provided_values=True,
        )
        branding.node.add_dependency(domain)

        for param_id, name, value in (
            ("UserPoolIdParam", cfg.ssm_user_pool_id, pool.user_pool_id),
            ("WebClientIdParam", cfg.ssm_web_client_id, web_client.user_pool_client_id),
            ("SimClientIdParam", cfg.ssm_sim_client_id, sim_client.user_pool_client_id),
        ):
            ssm.StringParameter(self, param_id, parameter_name=name, string_value=value)

        self.user_pool: cognito.IUserPool | None = pool
        self.web_client: cognito.IUserPoolClient | None = web_client
        self.sim_client: cognito.IUserPoolClient | None = sim_client
        self.domain: cognito.UserPoolDomain | None = domain

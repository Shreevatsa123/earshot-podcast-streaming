"""Cognito user pool and app clients.

Owner: M1 · Stack: base · Tracker: M1-02 (M1-03 for the sim-bot script) · Spec: CONTEXT §9 "Cognito", §7.2

STATUS: STUB. Creates nothing yet.

Must create:
- User pool: email sign-in, self sign-up, Essentials/Lite tier (free up to 10k MAU).
  Groups ``listeners`` and ``simulator``.
- App client ``web``: no secret, authorization code + PKCE, managed login. Callback and
  logout URLs are ``web_url`` and ``http://localhost:5173``.
- App client ``sim``: no secret, ``USER_PASSWORD_AUTH`` enabled.
- Managed login domain with prefix ``cfg.cognito_domain_prefix``.
- SSM String parameters ``cfg.ssm_user_pool_id``, ``cfg.ssm_web_client_id`` and
  ``cfg.ssm_sim_client_id``.

Inputs:
- ``web_url``: CloudFront URL from ``Web`` (None until M1's web construct exists).

Exposes (keep these names; ``Api`` and ``Web.publish`` read them):
- ``user_pool``, ``web_client``, ``sim_client``, ``domain``. Each is None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_cognito as cognito
from constructs import Construct

from earshot_infra.config import StageConfig


class Auth(Construct):
    def __init__(
        self, scope: Construct, construct_id: str, *, cfg: StageConfig, web_url: str | None
    ) -> None:
        super().__init__(scope, construct_id)
        self.user_pool: cognito.IUserPool | None = None
        self.web_client: cognito.IUserPoolClient | None = None
        self.sim_client: cognito.IUserPoolClient | None = None
        self.domain: cognito.UserPoolDomain | None = None
        # TODO(M1-02): implement per the docstring.

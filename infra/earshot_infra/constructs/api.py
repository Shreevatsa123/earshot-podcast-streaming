"""HTTP API, JWT authorizer, routes and the API Lambda.

Owner: M2 · Stack: base · Tracker: M2-04 (construct), M2-05/M2-06 (code) · Spec: CONTEXT §7

STATUS: STUB. Creates nothing yet.

Must create:
- API Lambda: ``common.python_function(name="api", handler="api.handler.main",
  memory_size=512)`` with env ``TABLE_NAME``, ``FLAGS_PARAM`` and ``ALLOWED_GENRES``.
  Grant read on ``core.table`` and ``core.flags_param``.
- HTTP API (payload 2.0):
  - JWT authorizer: issuer = ``auth.user_pool``, audience = both app client ids
  - CORS: origins ``web_url`` + ``http://localhost:5173``; methods GET, POST, OPTIONS;
    headers ``authorization``, ``content-type``, ``x-earshot-sim-user``
  - ``$default`` stage throttling: 500 req/s rate, 1000 burst
- Routes from §7.3 to the API Lambda (``GET /health`` without auth), and
  ``POST /events`` to ``ingest_function``.
- SSM String parameter ``cfg.ssm_api_url`` = the API endpoint.

Inputs (any of them may be None until their owner implements them; skip that part):
- ``core``, ``auth`` (M1), ``ingest_function`` (M3), ``web_url`` (M1)

Exposes (keep these names; ``Web.publish`` reads ``url``):
- ``http_api``, ``function``, ``url``. Each is None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.auth import Auth
from earshot_infra.constructs.core import Core


class Api(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: StageConfig,
        core: Core,
        auth: Auth,
        ingest_function: lambda_.IFunction | None,
        web_url: str | None,
    ) -> None:
        super().__init__(scope, construct_id)
        self.http_api: apigwv2.HttpApi | None = None
        self.function: lambda_.IFunction | None = None
        self.url: str | None = None
        # TODO(M2-04): implement per the docstring.

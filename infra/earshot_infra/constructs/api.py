"""HTTP API, JWT authorizer, routes and the API Lambda.

Owner: M2 · Stack: base · Tracker: M2-04 (construct), M2-05/M2-06 (code) · Spec: CONTEXT §7

Creates:
- API Lambda ``earshot-<stage>-api`` (``api.handler.main``, 512 MB) with env ``TABLE_NAME``,
  ``FLAGS_PARAM`` and ``ALLOWED_GENRES``; read access to ``core.table`` and the flags.
- HTTP API (payload 2.0) whose routes all need a Cognito access token by default:
  - JWT authorizer: issuer = ``auth.user_pool``, audience = the web and sim client ids.
    No scopes are required: web and sim tokens carry different ones.
  - CORS: origins ``web_url`` + ``http://localhost:5173``; methods GET, POST, OPTIONS;
    headers ``authorization``, ``content-type``, ``x-earshot-sim-user``. API Gateway
    answers the preflight ``OPTIONS`` itself.
  - ``$default`` stage, auto-deployed, throttled to 500 req/s with bursts of 1000.
- Routes (§7.3): the GET routes go to the API Lambda (``GET /health`` without auth), and
  ``POST /events`` goes to ``ingest_function``.
- SSM String parameter ``cfg.ssm_api_url`` = the API base URL (no trailing slash).

Inputs: ``core``, ``auth`` (M1), ``ingest_function`` (M3, may be None: then no
``POST /events``), ``web_url`` (M1, may be None: then only the localhost origin).
Without a user pool there's no authorizer, so the HTTP API isn't created at all rather
than left open.

Exposes (``Web.publish`` reads ``url``): ``http_api``, ``function``, ``url``.
"""

from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from earshot_infra.common import python_function
from earshot_infra.config import StageConfig
from earshot_infra.constructs.auth import Auth
from earshot_infra.constructs.core import Core

LOCAL_DEV_URL = "http://localhost:5173"
CORS_HEADERS = ["authorization", "content-type", "x-earshot-sim-user"]
THROTTLE_RATE = 500  # requests per second (§7.1)
THROTTLE_BURST = 1000

#: Read routes served by the API Lambda (§7.3). ``/health`` is the only one without auth.
READ_ROUTES = ("/health", "/genres", "/shows", "/shows/{showId}", "/progress/{episodeId}", "/trending", "/home")


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
        self.url: str | None = None

        function = python_function(
            self,
            "Function",
            cfg=cfg,
            name="api",
            handler="api.handler.main",
            memory_size=512,
            environment={
                "TABLE_NAME": cfg.table_name,
                "FLAGS_PARAM": cfg.ssm_flags,
                "ALLOWED_GENRES": cfg.allowed_genres,
            },
            description="Earshot read API (CONTEXT §7.3, §7.4)",
        )
        core.table.grant_read_data(function)
        core.flags_param.grant_read(function)
        self.function: lambda_.IFunction | None = function

        if auth.user_pool is None or auth.web_client is None or auth.sim_client is None:
            return

        jwt = authorizers.HttpUserPoolAuthorizer(
            "CognitoJwt", auth.user_pool, user_pool_clients=[auth.web_client, auth.sim_client]
        )
        http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=f"{cfg.prefix}-api",
            default_authorizer=jwt,
            create_default_stage=False,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=[url for url in (web_url, LOCAL_DEV_URL) if url],
                allow_methods=[apigwv2.CorsHttpMethod.GET, apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
                allow_headers=CORS_HEADERS,
                max_age=Duration.hours(1),
            ),
        )
        apigwv2.HttpStage(
            self,
            "DefaultStage",
            http_api=http_api,
            stage_name="$default",
            auto_deploy=True,
            throttle=apigwv2.ThrottleSettings(rate_limit=THROTTLE_RATE, burst_limit=THROTTLE_BURST),
        )

        api_integration = integrations.HttpLambdaIntegration("ApiLambda", function)
        for path in READ_ROUTES:
            http_api.add_routes(
                path=path,
                methods=[apigwv2.HttpMethod.GET],
                integration=api_integration,
                authorizer=apigwv2.HttpNoneAuthorizer() if path == "/health" else None,
            )
        if ingest_function is not None:
            http_api.add_routes(
                path="/events",
                methods=[apigwv2.HttpMethod.POST],
                integration=integrations.HttpLambdaIntegration("IngestLambda", ingest_function),
            )

        ssm.StringParameter(
            self,
            "ApiUrlParam",
            parameter_name=cfg.ssm_api_url,
            string_value=http_api.api_endpoint,
            description="Earshot API base URL (CONTEXT §7)",
        )
        self.http_api = http_api
        self.url = http_api.api_endpoint

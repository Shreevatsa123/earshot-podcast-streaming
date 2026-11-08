"""What every acceptance check receives (owner: M6 · tracker M6-07).

    ctx.cfg.table_name                          # every CONTEXT §9 name, via StageConfig
    ctx.client("dynamodb").get_item(...)        # boto3 clients in us-east-1, cached
    ctx.ssm_value(ctx.cfg.ssm_flags)            # read an SSM parameter
    resp = ctx.api.get("/home", sim_user="sim-000042")
    resp.status, resp.body, resp.elapsed_ms     # status code, parsed JSON, latency

The API client signs in as the ``sim-bot`` user (CONTEXT §9) the first time it's used, so
checks can act as any ``sim-*`` user (§7.2). It never raises on 4xx/5xx: checks look at
``resp.status`` themselves (S8 counts 5xx, for example).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from earshot_infra.config import StageConfig, names

#: Sign in again this many seconds before the token expires.
TOKEN_REFRESH_MARGIN_S = 300


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: Any  # parsed JSON, or the raw text if the body isn't JSON
    elapsed_ms: float


class ApiClient:
    def __init__(self, base_url: str, token: Callable[[], str], *, timeout_s: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout_s = timeout_s

    def get(self, path: str, *, sim_user: str | None = None, auth: bool = True) -> ApiResponse:
        return self.request("GET", path, sim_user=sim_user, auth=auth)

    def post(self, path: str, body: Any, *, sim_user: str | None = None) -> ApiResponse:
        return self.request("POST", path, body=body, sim_user=sim_user)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        sim_user: str | None = None,
        auth: bool = True,
    ) -> ApiResponse:
        headers = {"accept": "application/json"}
        if auth:
            headers["authorization"] = f"Bearer {self._token()}"
        if sim_user:
            headers["x-earshot-sim-user"] = sim_user
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["content-type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method, headers=headers
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as err:
            status, raw = err.code, err.read()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        text = raw.decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(text) if text else None
        except json.JSONDecodeError:
            parsed = text
        return ApiResponse(status=status, body=parsed, elapsed_ms=elapsed_ms)


class Context:
    def __init__(self, cfg: StageConfig, session: Any) -> None:
        self.cfg = cfg
        self.stage = cfg.stage
        self.session = session
        self._clients: dict[str, Any] = {}
        self._api: ApiClient | None = None
        self._token: str | None = None
        self._token_expires_at = 0.0

    @classmethod
    def from_aws(cls, stage: str, *, profile: str | None = None) -> Context:
        """Use your AWS credentials; the account comes from them."""
        import boto3

        session = boto3.Session(profile_name=profile, region_name=names.REGION)
        account = session.client("sts").get_caller_identity()["Account"]
        return cls(StageConfig(stage=stage, account=account), session)

    def client(self, service: str) -> Any:
        if service not in self._clients:
            self._clients[service] = self.session.client(service)
        return self._clients[service]

    def ssm_value(self, name: str, *, decrypt: bool = False) -> str:
        return self.client("ssm").get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]

    @property
    def api(self) -> ApiClient:
        if self._api is None:
            self._api = ApiClient(self.ssm_value(self.cfg.ssm_api_url), self.sim_token)
        return self._api

    def sim_token(self) -> str:
        """Cognito access token for ``sim-bot`` (cached until shortly before it expires)."""
        if self._token and time.time() < self._token_expires_at - TOKEN_REFRESH_MARGIN_S:
            return self._token
        result = self.client("cognito-idp").initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=self.ssm_value(self.cfg.ssm_sim_client_id),
            AuthParameters={
                "USERNAME": names.SIM_BOT_USERNAME,
                "PASSWORD": self.ssm_value(self.cfg.ssm_sim_password, decrypt=True),
            },
        )["AuthenticationResult"]
        self._token = result["AccessToken"]
        self._token_expires_at = time.time() + int(result.get("ExpiresIn", 3600))
        return self._token

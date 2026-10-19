"""Web hosting: private S3 bucket + CloudFront, and the runtime ``config.json``.

Owner: M1 · Stack: base · Tracker: M1-04 · Spec: CONTEXT §9 "Web runtime config"

STATUS: STUB. Creates nothing yet.

This construct has **two phases**, because Cognito needs the CloudFront URL and the web
config needs Cognito and API values:

1. ``__init__``, which runs first in the base stack. It must create:
   - private bucket ``cfg.web_bucket`` (block all public access, DESTROY + auto-delete)
   - CloudFront distribution with Origin Access Control
     (``origins.S3BucketOrigin.with_origin_access_control``), default root object
     ``index.html``, 403/404 -> ``/index.html`` with status 200 (SPA routing),
     ``PRICE_CLASS_100``
2. ``publish()``, called by the stack after ``Auth`` and ``Api`` exist. It must deploy:
   - ``web/dist`` (only if it exists, so the stack still deploys before the app is built)
   - ``config.json`` = ``{"apiUrl","region","userPoolId","webClientId","cognitoDomain","stage"}``
     via ``s3deploy.Source.json_data``, then invalidate CloudFront

Exposes (keep these names; ``Auth`` and ``Api`` read ``url``):
- ``bucket``, ``distribution``, ``url`` (``https://<id>.cloudfront.net``). Each is None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_s3 as s3
from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.auth import Auth


class Web(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        self._cfg = cfg
        self.bucket: s3.IBucket | None = None
        self.distribution: cloudfront.IDistribution | None = None
        self.url: str | None = None
        # TODO(M1-04): phase 1 per the docstring.

    def publish(self, *, api_url: str | None, auth: Auth) -> None:
        """Phase 2: deploy the built app and ``config.json``."""
        # TODO(M1-04): phase 2 per the docstring.

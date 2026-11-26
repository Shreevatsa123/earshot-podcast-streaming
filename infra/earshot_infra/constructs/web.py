"""Web hosting: private S3 bucket + CloudFront, and the runtime ``config.json``.

Owner: M1 · Stack: base · Tracker: M1-04 · Spec: CONTEXT §9 "Web runtime config"

This construct has **two phases**, because Cognito needs the CloudFront URL and the web
config needs Cognito and API values:

1. ``__init__``, which runs first in the base stack. It creates:
   - private bucket ``cfg.web_bucket`` (block all public access, TLS only, DESTROY +
     auto-delete: the site is rebuilt from git, so nothing in it needs keeping)
   - CloudFront distribution with Origin Access Control
     (``origins.S3BucketOrigin.with_origin_access_control``), HTTPS only, default root
     object ``index.html``, 403/404 -> ``/index.html`` with status 200 (SPA routing, so
     deep links like ``/browse`` load the app), ``PRICE_CLASS_100``, AWS's managed
     security-headers policy
2. ``publish()``, called by the stack after ``Auth`` and ``Api`` exist. It deploys, in one
   ``BucketDeployment``:
   - ``web/dist`` if it exists (``make deploy-base`` builds it first; CI synths without it),
     minus the local ``config.json`` from ``web/public``
   - ``config.json`` = ``{"apiUrl","region","userPoolId","webClientId","cognitoDomain","stage"}``
     via ``s3deploy.Source.json_data``. ``cognitoDomain`` is the managed login base URL
     (``https://<prefix>.auth.us-east-1.amazoncognito.com``). Values that don't exist yet
     are empty strings.
   - then invalidates ``/*`` on CloudFront, so a deploy shows up right away

Exposes (keep these names; ``Auth`` and ``Api`` read ``url``):
- ``bucket``, ``distribution``, ``url`` (``https://<id>.cloudfront.net``).
"""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from earshot_infra.config import REPO_ROOT, StageConfig
from earshot_infra.constructs.auth import Auth

WEB_DIST_DIR = REPO_ROOT / "web" / "dist"
CONFIG_FILE = "config.json"


class Web(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        self._cfg = cfg

        bucket = s3.Bucket(
            self,
            "Bucket",
            bucket_name=cfg.web_bucket,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # A 403/404 from S3 means "no such file": serve the app and let its router decide.
        spa_fallback = [
            cloudfront.ErrorResponse(
                http_status=status,
                response_http_status=200,
                response_page_path="/index.html",
                ttl=Duration.seconds(0),
            )
            for status in (403, 404)
        ]

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"{cfg.prefix} web app",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
            ),
            error_responses=spa_fallback,
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
        )

        self.bucket: s3.IBucket | None = bucket
        self.distribution: cloudfront.IDistribution | None = distribution
        self.url: str | None = f"https://{distribution.distribution_domain_name}"

    def publish(self, *, api_url: str | None, auth: Auth) -> None:
        """Phase 2: deploy the built app and ``config.json``, then invalidate CloudFront."""
        assert self.bucket is not None and self.distribution is not None

        config = {
            "apiUrl": api_url or "",
            "region": self._cfg.region,
            "userPoolId": auth.user_pool.user_pool_id if auth.user_pool else "",
            "webClientId": auth.web_client.user_pool_client_id if auth.web_client else "",
            "cognitoDomain": auth.domain.base_url() if auth.domain else "",
            "stage": self._cfg.stage,
        }

        sources = [s3deploy.Source.json_data(CONFIG_FILE, config)]
        if WEB_DIST_DIR.is_dir():
            # The build copies web/public/config.json (local dev values) into dist; leave it
            # out so the generated one above is the only config.json.
            sources.insert(0, s3deploy.Source.asset(str(WEB_DIST_DIR), exclude=[CONFIG_FILE]))

        s3deploy.BucketDeployment(
            self,
            "Deploy",
            destination_bucket=self.bucket,
            sources=sources,
            distribution=self.distribution,
            distribution_paths=["/*"],
            memory_limit=256,
        )

"""Persistent stack ``earshot-<stage>-base``: about $0 while idle (CONTEXT §5).

Owner: M6. **Members don't edit this file.** Fill in your own construct in
``earshot_infra/constructs/``. If you need a new input or output wired here, ask M6.

Rules:
- Never rename a construct id below ("Core", "Web", …). Renaming replaces the resources
  inside it, which means data loss for the table and bucket.
- Nothing here may reference the pipeline stack. Use names/ARNs from ``cfg`` (§5).
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Stack
from constructs import Construct

from earshot_infra.common import tag_owner, tag_stack
from earshot_infra.config import StageConfig
from earshot_infra.constructs.api import Api
from earshot_infra.constructs.auth import Auth
from earshot_infra.constructs.core import Core
from earshot_infra.constructs.ingest import Ingest
from earshot_infra.constructs.lake import Lake
from earshot_infra.constructs.monitoring import Monitoring
from earshot_infra.constructs.processing import ProcessingBase
from earshot_infra.constructs.recs import Recs
from earshot_infra.constructs.web import Web


class BaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        tag_stack(self, cfg)

        core = Core(self, "Core", cfg=cfg)
        tag_owner(core, "M6")

        # Web goes first: Auth (callback URLs) and Api (CORS) need its CloudFront URL.
        web = Web(self, "Web", cfg=cfg)
        auth = Auth(self, "Auth", cfg=cfg, web_url=web.url)
        tag_owner(web, "M1")
        tag_owner(auth, "M1")

        ingest = Ingest(self, "Ingest", cfg=cfg, core=core)
        tag_owner(ingest, "M3")

        api = Api(
            self,
            "Api",
            cfg=cfg,
            core=core,
            auth=auth,
            ingest_function=ingest.function,
            web_url=web.url,
        )
        tag_owner(api, "M2")

        # Phase 2 of Web: needs the API URL and Cognito ids for config.json.
        web.publish(api_url=api.url, auth=auth)

        processing = ProcessingBase(self, "Processing", cfg=cfg, core=core)
        tag_owner(processing, "M4")

        lake = Lake(self, "Lake", cfg=cfg, core=core)
        recs = Recs(self, "Recs", cfg=cfg, core=core, lake=lake)
        tag_owner(lake, "M5")
        tag_owner(recs, "M5")

        monitoring = Monitoring(self, "Monitoring", cfg=cfg, core=core)
        tag_owner(monitoring, "M6")

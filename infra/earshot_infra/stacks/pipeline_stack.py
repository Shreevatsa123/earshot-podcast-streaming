"""Ephemeral stack ``earshot-<stage>-pipeline``: the parts that cost money while they exist (CONTEXT §5).

Owner: M6. **Members don't edit this file.** Fill in your own construct in
``earshot_infra/constructs/``.

- The EC2 simulator bills by the hour.
- The two SQS triggers (event source mappings) make Lambda poll the queues even when
  they're empty, which uses SQS requests. The queues themselves are in base, so events
  sent while this stack is down wait there and are processed when it's back up.

Deploy only for tests and demos: ``make pipeline-up STAGE=x``. Always run
``make pipeline-down STAGE=x`` afterwards.

Base resources are referenced **by name/ARN from cfg**, never passed in as objects.
That avoids CloudFormation exports, so base can be updated while this stack is deployed
and this stack can be destroyed at any time.
"""

from __future__ import annotations

from typing import Any

from aws_cdk import Stack
from constructs import Construct

from earshot_infra.common import tag_owner, tag_stack
from earshot_infra.config import StageConfig
from earshot_infra.constructs.archiver import ArchiverPipeline
from earshot_infra.constructs.processing import ProcessingPipeline
from earshot_infra.constructs.simulator import Simulator


class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        tag_stack(self, cfg)

        processing = ProcessingPipeline(self, "Processing", cfg=cfg)
        tag_owner(processing, "M4")

        archiver = ArchiverPipeline(self, "Archiver", cfg=cfg)
        tag_owner(archiver, "M5")

        simulator = Simulator(self, "Simulator", cfg=cfg)
        tag_owner(simulator, "M3")

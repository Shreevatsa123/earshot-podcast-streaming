"""Ephemeral stack ``earshot-<stage>-pipeline``: the **hourly-billed** parts (CONTEXT §5).

Owner: M6. **Members don't edit this file.** Fill in your own construct in
``earshot_infra/constructs/``.

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
from earshot_infra.constructs.firehose import Firehose
from earshot_infra.constructs.processing import ProcessingPipeline
from earshot_infra.constructs.simulator import Simulator
from earshot_infra.constructs.stream import Stream


class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
        tag_stack(self, cfg)

        stream = Stream(self, "Stream", cfg=cfg)
        tag_owner(stream, "M3")

        processing = ProcessingPipeline(self, "Processing", cfg=cfg, stream=stream.stream)
        tag_owner(processing, "M4")

        firehose = Firehose(self, "Firehose", cfg=cfg, stream=stream.stream)
        tag_owner(firehose, "M5")

        simulator = Simulator(self, "Simulator", cfg=cfg)
        tag_owner(simulator, "M3")

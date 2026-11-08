"""SNS topic that every accepted playback event is published to (replaces the Kinesis stream).

Owner: M3 · Stack: base · Tracker: M3-03 · Spec: CONTEXT §5, §9, §10 "Event queues"

STATUS: STUB. Creates nothing yet.

Must create:
- ``sns.Topic`` named ``cfg.events_topic`` (``earshot-<stage>-events``): a standard topic
  (not FIFO), no encryption. It costs nothing while idle, so it lives in base.

Ingest publishes one message per accepted request (CONTEXT §7.5). The two consumers each
create their own queue and subscription: the hot queue in ``processing.py`` (M4) and the
cold queue in ``archiver.py`` (M5).

Exposes (keep this name; ``Ingest``, ``ProcessingBase`` and ``ArchiverBase`` read it):
- ``topic``. None until implemented.
"""

from __future__ import annotations

from aws_cdk import aws_sns as sns
from constructs import Construct

from earshot_infra.config import StageConfig


class EventsTopic(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig) -> None:
        super().__init__(scope, construct_id)
        self.topic: sns.ITopic | None = None
        # TODO(M3-03): implement per the docstring.

"""CloudWatch dashboard and alarms.

Owner: M6 · Stack: base · Tracker: M6-05 · Spec: CONTEXT §10 "Dashboard", "Alarms"

STATUS: STUB. Creates nothing yet.

Must create:
- Dashboard ``cfg.dashboard`` with the widgets in §10.
- At most 10 alarms, all notifying ``core.ops_topic``.

Build every metric from deterministic names (``cfg.function_name(...)``,
``cfg.stream_name``, ``cfg.table_name``, …), not from other constructs' attributes, so
monitoring works whatever state the other constructs are in.

Exposes: nothing.
"""

from __future__ import annotations

from constructs import Construct

from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class Monitoring(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, cfg: StageConfig, core: Core) -> None:
        super().__init__(scope, construct_id)
        # TODO(M6-05): implement per the docstring.

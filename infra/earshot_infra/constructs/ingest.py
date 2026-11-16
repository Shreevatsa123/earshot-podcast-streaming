"""Ingest Lambda for ``POST /events`` (the function only; M2 wires the route).

Owner: M3 · Stack: base · Tracker: M3-02 · Spec: CONTEXT §7.5, §10 "Message format"

Creates:
- ``common.python_function(name="ingest", handler="ingest.handler.main")`` with env
  ``TOPIC_ARN`` (``topic.topic_arn``) and ``ALLOWED_GENRES``.
- ``topic.grant_publish(function)``. The topic is in this stack (base), so the API
  accepts events even while the pipeline is down; they wait in the queues.

Inputs: ``core``; ``topic`` from ``EventsTopic`` (None until M3-03; create the function
without ``TOPIC_ARN`` or skip it until then).

Exposes (keep this name; ``Api`` reads it):
- ``function``: the ingest ``lambda_.Function`` (None only if ``topic`` is None).
"""

from __future__ import annotations

from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from constructs import Construct

from earshot_infra.common import python_function
from earshot_infra.config import StageConfig
from earshot_infra.constructs.core import Core


class Ingest(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cfg: StageConfig,
        core: Core,
        topic: sns.ITopic | None,
    ) -> None:
        super().__init__(scope, construct_id)
        self.function: lambda_.IFunction | None = None
        if topic is None:
            return

        function = python_function(
            self,
            "Function",
            cfg=cfg,
            name="ingest",
            handler="ingest.handler.main",
            environment={"TOPIC_ARN": topic.topic_arn, "ALLOWED_GENRES": cfg.allowed_genres},
            timeout_seconds=10,
            description="POST /events: validate, then publish one SNS message per request",
        )
        topic.grant_publish(function)
        self.function = function

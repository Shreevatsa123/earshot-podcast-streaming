#!/usr/bin/env python3
"""CDK entry point (owner: M6).

Use the Makefile (``make synth STAGE=<you>``), or from ``infra/``:
``cdk synth -c stage=<you> [-c alert_email=you@example.com]``.
"""

from __future__ import annotations

import os
import sys

import aws_cdk as cdk

from earshot_infra.config import PLACEHOLDER_ACCOUNT, StageConfig
from earshot_infra.stacks.base_stack import BaseStack
from earshot_infra.stacks.pipeline_stack import PipelineStack


def main() -> None:
    app = cdk.App()

    stage = app.node.try_get_context("stage")
    if not stage:
        sys.exit("Missing stage. Run: make synth STAGE=<yourname>  (or cdk synth -c stage=<yourname>)")

    # The CDK CLI sets CDK_DEFAULT_ACCOUNT from your AWS credentials.
    account = os.environ.get("CDK_DEFAULT_ACCOUNT")
    if not account:
        print(
            f"[earshot] No AWS credentials found: using placeholder account {PLACEHOLDER_ACCOUNT}. "
            "Fine for synth; deploying needs real credentials.",
            file=sys.stderr,
        )
        account = PLACEHOLDER_ACCOUNT

    try:
        cfg = StageConfig(
            stage=stage,
            account=account,
            alert_email=app.node.try_get_context("alert_email") or None,
        )
    except ValueError as err:
        sys.exit(str(err))

    env = cdk.Environment(account=cfg.account, region=cfg.region)
    BaseStack(
        app,
        cfg.stack_name("base"),
        cfg=cfg,
        env=env,
        description=f"Earshot {cfg.stage}: persistent resources (~$0 idle)",
    )
    PipelineStack(
        app,
        cfg.stack_name("pipeline"),
        cfg=cfg,
        env=env,
        description=f"Earshot {cfg.stage}: hourly-billed pipeline (tear down after use)",
    )
    app.synth()


if __name__ == "__main__":
    main()

"""Resource names and fixed identifiers for every stage (CONTEXT §8.3, §9).

This is the single source of truth for names. It is pure Python (stdlib only), so the
whole repo can import it:

- infra/ (CDK), through ``infra/earshot_infra/config.py``
- scripts/ and simulator/ (the Makefile runs scripts with ``PYTHONPATH=services:infra``)
- Lambda code, although Lambdas should read names from their environment variables (§9)

Contract content: change it only through a ``contract-change`` PR (CONTEXT §12).
"""

from __future__ import annotations

import os
import re

PROJECT = "earshot"
REGION = "us-east-1"

#: The fixed genres (CONTEXT §8.3): id -> display name, in display order.
GENRES: dict[str, str] = {
    "true-crime": "True Crime",
    "comedy": "Comedy",
    "news": "News",
    "technology": "Technology",
    "business": "Business",
    "science": "Science",
    "sports": "Sports",
    "history": "History",
}

#: Short names of the four Lambda functions (CONTEXT §9).
FUNCTIONS = ("api", "ingest", "processor", "recs-writer")
STACKS = ("base", "pipeline")

GLUE_TABLE = "events"

# S3 lake layout (CONTEXT §9)
LAKE_EVENTS_PREFIX = "events/"
LAKE_ERRORS_PREFIX = "errors/"
RECS_RUNS_PREFIX = "recs-runs/"
ATHENA_RESULTS_PREFIX = "athena-results/"

#: Initial value of the flags parameter (CONTEXT §9).
DEFAULT_FLAGS: dict[str, bool] = {"recs_enabled": True, "recs_fault_injection": False}

# 2-16 chars: starts with a letter; lowercase letters, digits, single inner hyphens.
_STAGE_RE = re.compile(r"[a-z](?:[a-z0-9]|-(?=[a-z0-9])){1,15}")
_ACCOUNT_RE = re.compile(r"\d{12}")


def validate_stage(stage: str) -> str:
    """Return ``stage`` if it's a valid stage name, otherwise raise ``ValueError``.

    Stage names end up in S3 bucket, Lambda and Cognito domain names, so they are strict:
    2-16 characters, lowercase letters, digits and single hyphens, starting with a letter
    (e.g. ``priya``, ``prod``).
    """
    if not isinstance(stage, str) or not _STAGE_RE.fullmatch(stage):
        raise ValueError(
            f"Invalid stage {stage!r}: use 2-16 lowercase letters, digits or single "
            "hyphens, starting with a letter (e.g. 'priya')."
        )
    return stage


def validate_account(account: str) -> str:
    """Return ``account`` if it's a 12-digit AWS account id, otherwise raise ``ValueError``."""
    if not isinstance(account, str) or not _ACCOUNT_RE.fullmatch(account):
        raise ValueError(f"Invalid AWS account id {account!r}: expected 12 digits.")
    return account


def prefix(stage: str) -> str:
    """``earshot-<stage>``: the start of almost every resource name."""
    return f"{PROJECT}-{validate_stage(stage)}"


# ---- Stacks and resources (CONTEXT §5, §9) -------------------------------------------


def stack_name(stage: str, kind: str) -> str:
    if kind not in STACKS:
        raise ValueError(f"Unknown stack {kind!r}; expected one of {STACKS}")
    return f"{prefix(stage)}-{kind}"


def table_name(stage: str) -> str:
    return f"{prefix(stage)}-main"


def lake_bucket(stage: str, account: str) -> str:
    return f"{prefix(stage)}-lake-{validate_account(account)}"


def web_bucket(stage: str, account: str) -> str:
    return f"{prefix(stage)}-web-{validate_account(account)}"


def stream_name(stage: str) -> str:
    return f"{prefix(stage)}-events"


def firehose_name(stage: str) -> str:
    return f"{prefix(stage)}-events-to-s3"


def glue_database(stage: str) -> str:
    return f"{PROJECT}_{validate_stage(stage).replace('-', '_')}"


def athena_workgroup(stage: str) -> str:
    return prefix(stage)


def qoe_topic(stage: str) -> str:
    return f"{prefix(stage)}-qoe-alerts"


def ops_topic(stage: str) -> str:
    return f"{prefix(stage)}-ops-alerts"


def processor_dlq(stage: str) -> str:
    return f"{prefix(stage)}-processor-dlq"


def state_machine(stage: str) -> str:
    return f"{prefix(stage)}-recs"


def dashboard(stage: str) -> str:
    return prefix(stage)


def cognito_domain_prefix(stage: str, account: str) -> str:
    return f"{prefix(stage)}-{validate_account(account)[-6:]}"


def function_name(stage: str, short_name: str) -> str:
    """Full Lambda name, e.g. ``function_name("priya", "recs-writer")``."""
    if short_name not in FUNCTIONS:
        raise ValueError(f"Unknown function {short_name!r}; expected one of {FUNCTIONS}")
    return f"{prefix(stage)}-{short_name}"


# ---- SSM parameters (CONTEXT §9) -------------------------------------------------------


def ssm_prefix(stage: str) -> str:
    return f"/{PROJECT}/{validate_stage(stage)}"


def ssm_api_url(stage: str) -> str:
    return f"{ssm_prefix(stage)}/api/url"


def ssm_user_pool_id(stage: str) -> str:
    return f"{ssm_prefix(stage)}/cognito/user-pool-id"


def ssm_web_client_id(stage: str) -> str:
    return f"{ssm_prefix(stage)}/cognito/web-client-id"


def ssm_sim_client_id(stage: str) -> str:
    return f"{ssm_prefix(stage)}/cognito/sim-client-id"


def ssm_flags(stage: str) -> str:
    return f"{ssm_prefix(stage)}/flags"


def ssm_sim_password(stage: str) -> str:
    return f"{ssm_prefix(stage)}/sim/password"


def ssm_podcastindex_key(stage: str) -> str:
    return f"{ssm_prefix(stage)}/podcastindex/key"


def ssm_podcastindex_secret(stage: str) -> str:
    return f"{ssm_prefix(stage)}/podcastindex/secret"


# ---- Lambda environment ----------------------------------------------------------------


def required_env(name: str) -> str:
    """Read a required Lambda environment variable (CONTEXT §9), with a clear error."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing environment variable {name}. Set it on the function in your "
            "construct (CONTEXT §9)."
        )
    return value

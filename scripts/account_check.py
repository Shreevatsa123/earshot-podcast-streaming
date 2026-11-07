#!/usr/bin/env python3
"""Print the AWS account limits that can block Earshot (owner: M6 · tracker M6-02, M6-03).

New accounts can start with low limits:
- Lambda concurrent executions: Earshot peaks around 55 (the S6 load test's 50 users on
  ``/home`` plus ingest and the processor), so it needs about 100. New accounts can start
  as low as 10. If it's lower, ask for 1000 (AWS's default; free, in Service Quotas).
- EC2 vCPUs for standard instances: the simulator's t3.micro needs 2.

Read-only. ``make service-check`` runs it; ``make account-check`` runs it alone.
Exit code: 0 = limits are fine, 1 = something should be raised, 2 = couldn't read them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_SERVICES_DIR = str(Path(__file__).resolve().parents[1] / "services")
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)

from shared.names import REGION  # noqa: E402

LAMBDA_CONCURRENCY_NEEDED = 100  # peak is about 55, during the S6 load test
LAMBDA_CONCURRENCY_REQUEST = 1000  # what to ask for if it's lower (AWS's default)
EC2_VCPUS_NEEDED = 2  # one t3.micro
#: "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances", counted in vCPUs.
EC2_STANDARD_VCPU_QUOTA = ("ec2", "L-1216C47A")


def lambda_concurrency(lambda_client: Any) -> int:
    return int(lambda_client.get_account_settings()["AccountLimit"]["ConcurrentExecutions"])


def ec2_vcpu_quota(quotas_client: Any) -> float:
    service, code = EC2_STANDARD_VCPU_QUOTA
    try:
        quota = quotas_client.get_service_quota(ServiceCode=service, QuotaCode=code)
    except Exception:  # not set on the account yet: AWS's default applies
        quota = quotas_client.get_aws_default_service_quota(ServiceCode=service, QuotaCode=code)
    return float(quota["Quota"]["Value"])


def check(lambda_client: Any, quotas_client: Any) -> tuple[str, int]:
    """Return the report text and the exit code."""
    lines = [f"Earshot account limits ({REGION})"]
    low = failed = False

    try:
        concurrency = lambda_concurrency(lambda_client)
    except Exception as err:
        failed = True
        lines.append(f"  - Lambda concurrent executions: couldn't read ({type(err).__name__}: {err})")
    else:
        if concurrency >= LAMBDA_CONCURRENCY_NEEDED:
            lines.append(
                f"  - Lambda concurrent executions: {concurrency} "
                f"(OK, Earshot needs about {LAMBDA_CONCURRENCY_NEEDED})"
            )
        else:
            low = True
            lines.append(
                f"  - Lambda concurrent executions: {concurrency} (LOW: Earshot needs about "
                f"{LAMBDA_CONCURRENCY_NEEDED}). Request {LAMBDA_CONCURRENCY_REQUEST}: "
                "Service Quotas -> AWS Lambda -> Concurrent executions."
            )

    try:
        vcpus = ec2_vcpu_quota(quotas_client)
    except Exception as err:
        failed = True
        lines.append(f"  - EC2 standard instance vCPUs: couldn't read ({type(err).__name__}: {err})")
    else:
        if vcpus >= EC2_VCPUS_NEEDED:
            lines.append(f"  - EC2 standard instance vCPUs: {vcpus:g} (OK, a t3.micro needs {EC2_VCPUS_NEEDED})")
        else:
            low = True
            lines.append(
                f"  - EC2 standard instance vCPUs: {vcpus:g} (TOO LOW: a t3.micro needs "
                f"{EC2_VCPUS_NEEDED}). Request more: Service Quotas -> Amazon EC2 -> "
                "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances."
            )

    return "\n".join(lines), 1 if low else 2 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the AWS limits that can block Earshot.")
    parser.add_argument("--profile", help="AWS CLI profile (default: your default credentials)")
    args = parser.parse_args(argv)
    try:
        import boto3
    except ImportError:
        print("boto3 isn't installed. Run `make install` first.", file=sys.stderr)
        return 2
    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    text, code = check(session.client("lambda"), session.client("service-quotas"))
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())

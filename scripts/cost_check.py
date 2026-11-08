#!/usr/bin/env python3
"""List resources in your AWS account that bill by the hour, or keep costing money.

Owner: M6 · Tracker: M6-08 · Spec: CONTEXT §5 (cost rules), §14 S10.

Run it after every working session (``make pipeline-down`` runs it for you):

    make cost-check

It checks the whole account in us-east-1, not only Earshot's resources, because the bill
covers the whole account. Read-only: it never changes or deletes anything.

Exit code: 0 = nothing hourly-billed is running, 1 = something is, 2 = the check couldn't
run completely (no credentials, missing permissions, ...).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SERVICES_DIR = str(Path(__file__).resolve().parents[1] / "services")
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)

from shared.names import PROJECT, REGION  # noqa: E402

#: Stacks that should only exist during a test or demo session.
SESSION_STACK_SUFFIXES = {"-pipeline": "pipeline-down", "-servicecheck": "service-check-down"}

#: boto3 clients the checks use.
SERVICES = ("cloudformation", "kinesis", "firehose", "ec2", "elbv2")


@dataclass(frozen=True)
class Finding:
    """One resource that costs money while it exists."""

    kind: str
    name: str
    detail: str
    hourly: bool  # True: bills for every hour it exists. False: a smaller leftover.
    earshot: bool  # Its name or tags say it's one of ours.


@dataclass(frozen=True)
class Clients:
    cloudformation: Any
    kinesis: Any
    firehose: Any
    ec2: Any
    elbv2: Any

    @classmethod
    def from_factory(cls, make_client: Callable[[str], Any]) -> Clients:
        """Build from anything that turns a service name into a client (e.g. ``session.client``)."""
        return cls(**{service: make_client(service) for service in SERVICES})


def _items(client: Any, operation: str, key: str) -> Iterator[dict[str, Any]]:
    """Every item under ``key`` across all pages of a paginated boto3 call."""
    for page in client.get_paginator(operation).paginate():
        yield from page.get(key, [])


def _tag(tags: list[dict[str, str]] | None, key: str) -> str | None:
    return next((t.get("Value") for t in tags or [] if t.get("Key") == key), None)


def _is_earshot(name: str, tags: list[dict[str, str]] | None = None) -> bool:
    return PROJECT in name.lower() or _tag(tags, "project") == PROJECT


# ---- Checks (each takes one boto3 client and returns findings) ------------------------


def check_stacks(cloudformation: Any) -> list[Finding]:
    found = []
    for stack in _items(cloudformation, "describe_stacks", "Stacks"):
        name = stack["StackName"]
        for suffix, make_target in SESSION_STACK_SUFFIXES.items():
            if name.startswith(f"{PROJECT}-") and name.endswith(suffix):
                stage = name[len(PROJECT) + 1 : -len(suffix)]
                found.append(
                    Finding(
                        "CloudFormation stack",
                        name,
                        f"{stack.get('StackStatus', '?')}; remove it with "
                        f"`make {make_target} STAGE={stage}`",
                        hourly=False,  # the stack is free; what's inside it is listed below
                        earshot=True,
                    )
                )
    return found


def check_kinesis(kinesis: Any) -> list[Finding]:
    found = []
    for name in _items(kinesis, "list_streams", "StreamNames"):
        summary = kinesis.describe_stream_summary(StreamName=name)["StreamDescriptionSummary"]
        status = summary.get("StreamStatus", "?")
        mode = summary.get("StreamModeDetails", {}).get("StreamMode", "PROVISIONED")
        detail = f"{status}, {mode.lower()}"
        if mode == "PROVISIONED" and "OpenShardCount" in summary:
            detail += f", {summary['OpenShardCount']} shard(s), ~$0.015/shard-hour"
        found.append(
            Finding("Kinesis stream", name, detail, hourly=status != "DELETING", earshot=_is_earshot(name))
        )
    return found


def check_firehose(firehose: Any) -> list[Finding]:
    found: list[Finding] = []
    start: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Limit": 100}
        if start:
            kwargs["ExclusiveStartDeliveryStreamName"] = start
        response = firehose.list_delivery_streams(**kwargs)
        stream_names = response.get("DeliveryStreamNames", [])
        found += [
            Finding(
                "Firehose stream",
                name,
                "billed per GB delivered, not hourly; it means a pipeline stack is still up",
                hourly=False,
                earshot=_is_earshot(name),
            )
            for name in stream_names
        ]
        if not response.get("HasMoreDeliveryStreams") or not stream_names:
            return found
        start = stream_names[-1]


def check_instances(ec2: Any) -> list[Finding]:
    found = []
    for reservation in _items(ec2, "describe_instances", "Reservations"):
        for instance in reservation.get("Instances", []):
            state = instance.get("State", {}).get("Name", "?")
            if state in ("shutting-down", "terminated"):
                continue
            tags = instance.get("Tags")
            label = _tag(tags, "Name")
            name = f"{instance['InstanceId']} ({label})" if label else instance["InstanceId"]
            running = state in ("pending", "running", "stopping")
            detail = f"{instance.get('InstanceType', '?')}, {state}"
            if not running:
                detail += ": a stopped instance doesn't bill, but its disk does"
            found.append(
                Finding("EC2 instance", name, detail, hourly=running, earshot=_is_earshot(name, tags))
            )
    return found


def check_addresses(ec2: Any) -> list[Finding]:
    found = []
    for address in ec2.describe_addresses().get("Addresses", []):
        name = address.get("PublicIp") or address.get("AllocationId", "?")
        attached = f"attached to {address['InstanceId']}" if address.get("InstanceId") else "not attached"
        found.append(
            Finding(
                "Elastic IP",
                name,
                f"{attached}; $0.005/hour either way",
                hourly=True,
                earshot=_is_earshot(name, address.get("Tags")),
            )
        )
    return found


def check_nat_gateways(ec2: Any) -> list[Finding]:
    # Filtered here instead of in the call: describe_nat_gateways spells it `Filter`,
    # unlike the other describe calls.
    return [
        Finding(
            "NAT gateway",
            gateway["NatGatewayId"],
            f"{gateway['State']}; ~$0.045/hour plus data, and not allowed (CONTEXT §0)",
            hourly=True,
            earshot=_is_earshot(gateway["NatGatewayId"], gateway.get("Tags")),
        )
        for gateway in _items(ec2, "describe_nat_gateways", "NatGateways")
        if gateway.get("State") in ("pending", "available")
    ]


def check_volumes(ec2: Any) -> list[Finding]:
    return [
        Finding(
            "EBS volume",
            volume["VolumeId"],
            f"{volume.get('Size', '?')} GiB, not attached; billed per GB-month",
            hourly=False,
            earshot=_is_earshot(volume["VolumeId"], volume.get("Tags")),
        )
        for volume in _items(ec2, "describe_volumes", "Volumes")
        if volume.get("State") == "available"
    ]


def check_load_balancers(elbv2: Any) -> list[Finding]:
    return [
        Finding(
            "Load balancer",
            lb["LoadBalancerName"],
            f"{lb.get('Type', '?')}; bills hourly, and not allowed (CONTEXT §0)",
            hourly=True,
            earshot=_is_earshot(lb["LoadBalancerName"]),
        )
        for lb in _items(elbv2, "describe_load_balancers", "LoadBalancers")
    ]


CHECKS: tuple[tuple[str, str, Callable[[Any], list[Finding]]], ...] = (
    ("CloudFormation stacks", "cloudformation", check_stacks),
    ("Kinesis streams", "kinesis", check_kinesis),
    ("Firehose streams", "firehose", check_firehose),
    ("EC2 instances", "ec2", check_instances),
    ("Elastic IPs", "ec2", check_addresses),
    ("NAT gateways", "ec2", check_nat_gateways),
    ("EBS volumes", "ec2", check_volumes),
    ("Load balancers", "elbv2", check_load_balancers),
)


def run_checks(clients: Clients) -> tuple[list[Finding], list[str]]:
    """Run every check. A check that fails (e.g. access denied) is reported, not fatal."""
    findings: list[Finding] = []
    failures: list[str] = []
    for label, client_name, check in CHECKS:
        try:
            findings.extend(check(getattr(clients, client_name)))
        except Exception as err:  # one denied call shouldn't hide the other checks
            failures.append(f"{label}: {type(err).__name__}: {err}")
    return findings, failures


def exit_code(findings: list[Finding], failures: list[str]) -> int:
    if any(f.hourly for f in findings):
        return 1
    return 2 if failures else 0


def report(findings: list[Finding], failures: list[str]) -> str:
    hourly = [f for f in findings if f.hourly]
    leftovers = [f for f in findings if not f.hourly]
    lines = [f"Earshot cost check: whole account, {REGION}"]
    for title, group in (("BILLING EVERY HOUR", hourly), ("OTHER LEFTOVERS", leftovers)):
        if group:
            lines += ["", f"{title}:"]
            lines += [
                f"  - {f.kind}: {f.name}{' [earshot]' if f.earshot else ''}: {f.detail}" for f in group
            ]
    if failures:
        lines += ["", "COULDN'T CHECK:"] + [f"  - {message}" for message in failures]
    lines.append("")
    if hourly:
        lines.append(
            f"RESULT: {len(hourly)} hourly-billed resource(s) running. If they're Earshot's, "
            "run `make pipeline-down STAGE=<stage>`; otherwise stop them in the AWS console."
        )
    elif failures:
        lines.append("RESULT: nothing hourly-billed found, but some checks couldn't run (above).")
    else:
        lines.append("RESULT: OK, nothing hourly-billed is running.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List AWS resources that bill by the hour (read-only, whole account)."
    )
    parser.add_argument("--profile", help="AWS CLI profile (default: your default credentials)")
    args = parser.parse_args(argv)

    try:
        import boto3
    except ImportError:
        print("boto3 isn't installed. Run `make install` first.", file=sys.stderr)
        return 2

    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    try:
        session.client("sts").get_caller_identity()
    except Exception as err:
        print(
            f"Can't use your AWS credentials ({type(err).__name__}). "
            f"Run `aws configure` (region {REGION}) and try again.",
            file=sys.stderr,
        )
        return 2

    findings, failures = run_checks(Clients.from_factory(session.client))
    print(report(findings, failures))
    return exit_code(findings, failures)


if __name__ == "__main__":
    sys.exit(main())

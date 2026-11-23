"""Command line for the simulator: ``python -m simulator {generate,replay,run} ...`` (CONTEXT §11)."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from simulator import DEFAULT_CATALOG, ROOT  # sets up sys.path for shared/

from shared import clock, names  # noqa: E402

from simulator.generate import generate_events, read_jsonl, write_jsonl  # noqa: E402
from simulator.model import Catalog, Population  # noqa: E402

SIM_USERNAME = "sim-bot@earshot.test"


def _start_ms(value: str | None) -> int:
    """``--start`` as ISO date/time (UTC) or epoch ms; default: 24 h ago."""
    if value is None:
        return clock.now_ms() - 24 * 3600 * 1000
    if value.isdigit():
        return int(value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _boto3_client(service: str):
    import boto3

    return boto3.client(service, region_name=os.environ.get("AWS_DEFAULT_REGION", names.REGION))


def _ssm_value(ssm, name: str, *, decrypt: bool = False) -> str:
    return ssm.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]


# ---- subcommands -----------------------------------------------------------------------


def cmd_generate(args: argparse.Namespace) -> int:
    catalog = Catalog.load(args.catalog)
    events = generate_events(
        catalog,
        users=args.users,
        events=args.events,
        seed=args.seed,
        start_ms=_start_ms(args.start),
        window_ms=int(args.window_hours * 3600 * 1000),
        shuffle=args.shuffle,
        dup_rate=args.dup_rate,
    )
    write_jsonl(args.out, events)
    unique = len({e["event_id"] for e in events})
    print(f"wrote {len(events)} events ({unique} unique) from {args.users} users to {args.out}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    from simulator.replay import replay

    if not args.direct:
        print("Only --direct is supported: it publishes straight to the SNS events topic.", file=sys.stderr)
        return 2
    topic_arn = args.topic_arn
    if not topic_arn:
        account = _boto3_client("sts").get_caller_identity()["Account"]
        topic_arn = f"arn:aws:sns:{names.REGION}:{account}:{names.events_topic(args.stage)}"
    report = replay(
        read_jsonl(args.file), sns=_boto3_client("sns"), topic_arn=topic_arn, keep_server_ts=args.keep_server_ts
    )
    print(json.dumps(report, indent=2))
    return 0 if report["failed_messages"] == 0 else 1


def cmd_run(args: argparse.Namespace) -> int:
    from simulator.run import HttpEventsApi, TokenProvider, run

    ssm = _boto3_client("ssm")
    api_url = args.api_url or _ssm_value(ssm, names.ssm_api_url(args.stage))
    client_id = args.client_id or _ssm_value(ssm, names.ssm_sim_client_id(args.stage))
    password = os.environ.get("EARSHOT_SIM_PASSWORD") or _ssm_value(
        ssm, names.ssm_sim_password(args.stage), decrypt=True
    )
    tokens = TokenProvider(_boto3_client("cognito-idp"), client_id, args.username, password)
    tokens.get()  # fail fast on bad credentials

    rng = random.Random(args.seed)
    population = Population(Catalog.load(args.catalog), args.users, rng)
    print(
        f"run: stage={args.stage} users={args.users} rate={args.rate}/s duration={args.duration}s "
        f"api={api_url}",
        flush=True,
    )
    report = run(
        population,
        api=HttpEventsApi(api_url),
        tokens=tokens.get,
        rate=args.rate,
        duration_sec=args.duration,
        workers=args.workers,
    )
    report["stage"] = args.stage
    out = Path(args.report or ROOT / "runs" / f"{report['run_id']}.run-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"report written to {out}")
    return 0


# ---- parser ------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simulator", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write events to a JSON Lines file (no AWS)")
    gen.add_argument("--out", required=True)
    gen.add_argument("--users", type=int, default=200)
    gen.add_argument("--events", type=int, default=10_000, help="number of lines, duplicates included")
    gen.add_argument("--shuffle", action="store_true")
    gen.add_argument("--dup-rate", type=float, default=0.0)
    gen.add_argument("--seed", type=int, default=7)
    gen.add_argument("--start", help="first event time: ISO (UTC) or epoch ms; default 24 h ago")
    gen.add_argument("--window-hours", type=float, default=24.0)
    gen.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    gen.set_defaults(func=cmd_generate)

    rep = sub.add_parser("replay", help="publish a JSON Lines file to the SNS events topic")
    rep.add_argument("--file", required=True)
    rep.add_argument("--direct", action="store_true", help="publish straight to SNS (required)")
    rep.add_argument("--stage", required=True)
    rep.add_argument("--topic-arn", help="default: earshot-<stage>-events in the current account")
    rep.add_argument("--keep-server-ts", action="store_true", help="keep the file's server_ts")
    rep.set_defaults(func=cmd_replay)

    run_ = sub.add_parser("run", help="send live traffic through POST /events")
    run_.add_argument("--stage", required=True)
    run_.add_argument("--users", type=int, default=2000)
    run_.add_argument("--rate", type=float, default=100, help="events per second")
    run_.add_argument("--duration", type=float, default=60, help="seconds")
    run_.add_argument("--seed", type=int, default=42)
    run_.add_argument("--workers", type=int, default=16)
    run_.add_argument("--api-url", help="default: SSM /earshot/<stage>/api/url")
    run_.add_argument("--client-id", help="default: SSM /earshot/<stage>/cognito/sim-client-id")
    run_.add_argument("--username", default=SIM_USERNAME)
    run_.add_argument("--report", help="default: runs/<run_id>.run-report.json (git-ignored)")
    run_.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    run_.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

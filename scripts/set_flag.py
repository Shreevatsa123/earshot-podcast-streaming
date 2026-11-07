#!/usr/bin/env python3
"""Show or change the feature flags in SSM ``/earshot/<stage>/flags`` (CONTEXT §9).

Owner: M2 · Tracker: M2-08 · Used by: S8 (graceful degradation) and the demo runbook

    python scripts/set_flag.py --stage <stage>                          # show the flags
    python scripts/set_flag.py --stage <stage> recs_enabled=false       # change one or more
    python scripts/set_flag.py --stage <stage> --reset                  # back to the defaults

For prod, put ``AWS_PROFILE=earshot-prod`` in front. The API caches the flags for 10 s
(§9), so ``/home`` follows a change within about 10 s.

Flags (values ``true`` or ``false``):
- ``recs_enabled``: personalized rows on ``/home`` (§7.4 rule 3)
- ``recs_fault_injection``: make the recs lookup fail, to test the fallback (§7.4 rule 4)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SERVICES_DIR = str(Path(__file__).resolve().parents[1] / "services")
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)

from shared import names  # noqa: E402

_BOOLS = {"true": True, "false": False}

Flags = dict[str, bool]


def parse_changes(assignments: list[str]) -> Flags:
    """``["recs_enabled=false"]`` -> ``{"recs_enabled": False}``. Raises ``ValueError`` otherwise."""
    changes: Flags = {}
    for assignment in assignments:
        flag, sep, value = assignment.partition("=")
        if flag not in names.DEFAULT_FLAGS:
            raise ValueError(f"Unknown flag {flag!r}; use one of {sorted(names.DEFAULT_FLAGS)}")
        if not sep or value.lower() not in _BOOLS:
            raise ValueError(f"Use {flag}=true or {flag}=false, not {assignment!r}")
        changes[flag] = _BOOLS[value.lower()]
    return changes


def update_flags(ssm: Any, parameter: str, changes: Flags, *, reset: bool = False) -> tuple[Flags, Flags]:
    """Apply ``changes`` to the stored flags (or to the defaults if ``reset``) and return
    ``(before, after)``. Writes only when something changed; with no changes and no reset,
    it only reads."""
    before = json.loads(ssm.get_parameter(Name=parameter)["Parameter"]["Value"])
    if not changes and not reset:
        return before, before
    after = {**names.DEFAULT_FLAGS, **({} if reset else before), **changes}
    if after != before:
        ssm.put_parameter(
            Name=parameter, Value=json.dumps(after, separators=(",", ":")), Type="String", Overwrite=True
        )
    return before, after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show or change Earshot feature flags (CONTEXT §9).")
    parser.add_argument("--stage", required=True, help="e.g. prod")
    parser.add_argument("--reset", action="store_true", help=f"start from the defaults {names.DEFAULT_FLAGS}")
    parser.add_argument("changes", nargs="*", metavar="FLAG=true|false")
    args = parser.parse_args(argv)
    try:
        names.validate_stage(args.stage)
        changes = parse_changes(args.changes)
    except ValueError as err:
        parser.error(str(err))

    import boto3

    ssm = boto3.client("ssm", region_name=names.REGION)
    parameter = names.ssm_flags(args.stage)
    try:
        before, after = update_flags(ssm, parameter, changes, reset=args.reset)
    except ssm.exceptions.ParameterNotFound:
        print(f"{parameter} doesn't exist. Deploy the base stack first.", file=sys.stderr)
        return 1

    if after == before:
        print(f"{parameter}: {json.dumps(after)}" + (" (unchanged)" if changes or args.reset else ""))
    else:
        print(f"{parameter}: {json.dumps(before)} -> {json.dumps(after)}")
        print("The API picks this up within about 10 s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

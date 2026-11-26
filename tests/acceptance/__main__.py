"""``python -m acceptance --stage prod [--only S1,S10]`` (or ``make acceptance STAGE=prod``)."""

from __future__ import annotations

import argparse
import sys

from acceptance import harness


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m acceptance",
        description="Run the S1–S10 acceptance checks (CONTEXT §14) against a deployed stage.",
    )
    parser.add_argument("--stage", required=True, help="Stage to test, e.g. prod")
    parser.add_argument("--only", help="Comma-separated criteria, e.g. S1,S10 (default: all)")
    parser.add_argument("--profile", help="AWS CLI profile (default: your default credentials)")
    parser.add_argument(
        "--no-write", action="store_true", help=f"Don't update {harness.RESULTS_FILE.name}"
    )
    args = parser.parse_args(argv)

    try:
        checks = harness.select(harness.discover(), args.only.split(",") if args.only else None)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2

    try:
        from acceptance.context import Context

        ctx = Context.from_aws(args.stage, profile=args.profile)
    except ImportError:
        print("boto3 isn't installed. Run `make install` first.", file=sys.stderr)
        return 2
    except Exception as err:
        print(f"Can't start ({type(err).__name__}: {err}). Check `aws configure`.", file=sys.stderr)
        return 2

    results = [harness.run_check(check, ctx) for check in checks]
    print(harness.summary(results))
    report = harness.write_report(results, args.stage)
    print(f"\nRaw results: {report.relative_to(harness.REPO_ROOT)}")

    if args.stage == harness.RESULTS_STAGE and not args.no_write:
        written = harness.write_results_file(results, args.stage)
        if written:
            print(f"Updated {harness.RESULTS_FILE.relative_to(harness.REPO_ROOT)}: {', '.join(written)}")
    else:
        print(f"{harness.RESULTS_FILE.name} only records {harness.RESULTS_STAGE} results; not changed.")
    return harness.exit_code(results)


if __name__ == "__main__":
    sys.exit(main())

"""Runner for the S1–S10 acceptance checks (owner: M6 · tracker M6-07).

A check is a module ``acceptance/s<N>_<name>.py`` with:

    CRITERION = "S3"                  # id from CONTEXT §14; must match the file's number
    TITLE = "Bad-input correctness"
    OWNER = "M4"
    TARGET = "10k shuffled events with 10 % duplicates -> 0 wrong positions, 0 double counts"

    def run(ctx: Context) -> Measurement:
        ...
        return Measurement(passed=wrong == 0 and doubled == 0,
                           measured=f"{wrong} wrong positions, {doubled} double counts",
                           details={"events": 10_000})

``run`` raising ``NotImplementedError`` means "not written yet". Any other exception is
reported as ERROR, so one broken check never hides the others.

Where results go:
- Always: a summary on screen and raw JSON in ``tests/acceptance/output/`` (not committed).
- Only for ``STAGE=prod``: the matching rows of ``docs/results.md``. PASS, FAIL and ERROR
  replace a row; NOT IMPLEMENTED never does, so a result recorded by hand isn't lost.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any

PACKAGE = "acceptance"
REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = REPO_ROOT / "docs" / "results.md"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
RESULTS_STAGE = "prod"

TABLE_START = "<!-- results:start -->"
TABLE_END = "<!-- results:end -->"
TABLE_HEADER = (
    "| # | Criterion | Target | Owner | Status | Measured | Last run (UTC) |",
    "|---|---|---|---|---|---|---|",
)

_MODULE_RE = re.compile(r"s(\d+)_[a-z0-9_]+")
_CRITERION_RE = re.compile(r"S(\d+)")
_ROW_RE = re.compile(r"\|\s*(S\d+)\s*\|")


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    NOT_IMPLEMENTED = "NOT IMPLEMENTED"
    NOT_RUN = "NOT RUN"


@dataclass(frozen=True)
class Measurement:
    """What a check's ``run(ctx)`` returns."""

    passed: bool
    measured: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Check:
    criterion: str
    title: str
    owner: str
    target: str
    module: ModuleType

    @property
    def number(self) -> int:
        return int(self.criterion[1:])


@dataclass(frozen=True)
class Result:
    criterion: str
    title: str
    owner: str
    target: str
    status: Status
    measured: str
    details: dict[str, Any]
    started_at: str  # "YYYY-MM-DD HH:MM", UTC
    duration_s: float


# ---- Finding and running checks ---------------------------------------------------------


def discover(package: str = PACKAGE) -> list[Check]:
    """Every ``s<N>_*.py`` check in the package, sorted S1, S2, …, S10."""
    pkg = importlib.import_module(package)
    checks = []
    for info in pkgutil.iter_modules(pkg.__path__):
        match = _MODULE_RE.fullmatch(info.name)
        if match:
            check = as_check(importlib.import_module(f"{package}.{info.name}"))
            if check.number != int(match.group(1)):
                raise ValueError(f"{info.name}.py says CRITERION = {check.criterion!r}; the file name says S{match.group(1)}")
            checks.append(check)
    checks.sort(key=lambda c: c.number)
    seen = [c.criterion for c in checks]
    if len(seen) != len(set(seen)):
        raise ValueError(f"Duplicate criteria: {seen}")
    return checks


def as_check(module: ModuleType) -> Check:
    missing = [name for name in ("CRITERION", "TITLE", "OWNER", "TARGET", "run") if not hasattr(module, name)]
    if missing:
        raise ValueError(f"{module.__name__} is missing {', '.join(missing)}")
    if not _CRITERION_RE.fullmatch(str(module.CRITERION)):
        raise ValueError(f"{module.__name__}: CRITERION must look like 'S3', not {module.CRITERION!r}")
    return Check(module.CRITERION, module.TITLE, module.OWNER, module.TARGET, module)


def select(checks: Sequence[Check], only: Iterable[str] | None) -> list[Check]:
    """The checks named in ``only`` (e.g. ``["S1", "s10"]``), or all of them."""
    wanted = {c.strip().upper() for c in only or [] if c.strip()}
    if not wanted:
        return list(checks)
    known = [c.criterion for c in checks]
    unknown = sorted(wanted - set(known))
    if unknown:
        raise ValueError(f"Unknown criteria {unknown}; choose from {', '.join(known)}")
    return [c for c in checks if c.criterion in wanted]


def run_check(check: Check, ctx: Any) -> Result:
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    details: dict[str, Any] = {}
    try:
        measurement = check.module.run(ctx)
        if not isinstance(measurement, Measurement):
            raise TypeError(f"run() must return a Measurement, not {type(measurement).__name__}")
        status = Status.PASS if measurement.passed else Status.FAIL
        measured, details = measurement.measured, dict(measurement.details)
    except NotImplementedError as err:
        status, measured = Status.NOT_IMPLEMENTED, str(err) or "not written yet"
    except Exception as err:  # report it; one broken check mustn't hide the rest
        status, measured = Status.ERROR, f"{type(err).__name__}: {err}"
    return Result(
        criterion=check.criterion,
        title=check.title,
        owner=check.owner,
        target=check.target,
        status=status,
        measured=measured,
        details=details,
        started_at=started.strftime("%Y-%m-%d %H:%M"),
        duration_s=round(time.monotonic() - t0, 2),
    )


def exit_code(results: Iterable[Result]) -> int:
    return 1 if any(r.status in (Status.FAIL, Status.ERROR) for r in results) else 0


def summary(results: Sequence[Result]) -> str:
    return "\n".join(
        f"{r.criterion:<4} {r.status.value:<16} {r.title}: {r.measured}" for r in results
    )


# ---- Writing results ---------------------------------------------------------------------


def _cell(text: Any) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render_row(
    criterion: str, title: str, target: str, owner: str, status: str, measured: str = "", last_run: str = ""
) -> str:
    cells = (criterion, title, target, owner, status, measured, last_run)
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def result_row(result: Result, stage: str) -> str:
    return render_row(
        result.criterion, result.title, result.target, result.owner, result.status.value,
        result.measured, f"{result.started_at} ({stage})",
    )


def blank_table(checks: Sequence[Check]) -> str:
    """The results table with every criterion NOT RUN (used to create docs/results.md)."""
    rows = [render_row(c.criterion, c.title, c.target, c.owner, Status.NOT_RUN.value) for c in checks]
    return "\n".join([TABLE_START, *TABLE_HEADER, *rows, TABLE_END])


def update_results_table(text: str, rows: Mapping[str, str]) -> str:
    """Replace the rows for the given criteria (``{"S3": "| S3 | … |"}``) between the markers.

    Rows for other criteria, and everything outside the markers, stay as they are. A
    criterion that has no row yet is added at the end of the table.
    """
    start, end = text.find(TABLE_START), text.find(TABLE_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"The results file needs {TABLE_START} and {TABLE_END} around the table")
    head = text[: start + len(TABLE_START)]
    body = text[start + len(TABLE_START) : end].strip("\n").splitlines()
    tail = text[end:]

    remaining = dict(rows)
    lines = []
    for line in body:
        match = _ROW_RE.match(line)
        lines.append(remaining.pop(match.group(1)) if match and match.group(1) in remaining else line)
    lines += [remaining[c] for c in sorted(remaining, key=lambda c: int(c[1:]))]
    return head + "\n" + "\n".join(lines) + "\n" + tail


def write_results_file(results: Iterable[Result], stage: str, path: Path = RESULTS_FILE) -> list[str]:
    """Update ``docs/results.md`` with real outcomes. Returns the criteria written."""
    rows = {r.criterion: result_row(r, stage) for r in results if r.status is not Status.NOT_IMPLEMENTED}
    if rows:
        path.write_text(update_results_table(path.read_text(encoding="utf-8"), rows), encoding="utf-8")
    return sorted(rows, key=lambda c: int(c[1:]))


def write_report(results: Iterable[Result], stage: str, output_dir: Path = OUTPUT_DIR) -> Path:
    """Save every result, including details, as JSON for later analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"{stage}-{stamp}.json"
    payload = {"stage": stage, "results": [asdict(r) for r in results]}
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path

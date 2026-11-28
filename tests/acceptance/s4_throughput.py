"""S4 · Throughput with no data loss.

Owner: M3 + M6 · Spec: CONTEXT §14 S4, §7.5 ("lost event"), §11 (run report).

How to run it:
1. Send the load with the simulator (on the EC2 instance, or from your machine):
   ``python -m simulator run --stage <s> --users 2000 --rate 500 --duration 600 --seed 42``.
   It writes ``runs/<run_id>.run-report.json``.
2. ``make acceptance STAGE=<s> ONLY=S4``. The check reads the newest report in ``runs/``,
   or the file named in ``S4_RUN_REPORT`` (copy it there if the run was on EC2).
   The pipeline stack must be up, so the queues get drained.

What it checks, for the run's ``server_ts`` window ``[start_ms, end_ms]``:
- **Load:** the run lasted ≥ 600 s at ≥ 95 % of 500 events/s.
- **Accepted:** ``accepted`` in the run report (what the API said it took, §7.5).
- **Processed:** the hot and cold queues drain to 0 and both DLQs stay empty, so every
  accepted message was consumed without failing.
- **Stored:** distinct ``event_id`` in Athena (``athena/count_events.sql``, M5).
Pass if the load target was met, the queues drained, the DLQs are empty and
stored == accepted (0 lost). ``EventsAccepted`` from CloudWatch is reported too, as a
cross-check; it isn't part of the verdict because other traffic in the stage adds to it.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from acceptance.harness import REPO_ROOT, Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

CRITERION = "S4"
TITLE = "Throughput, no loss"
OWNER = "M3 + M6"
TARGET = "500 events/s for 10 min; accepted = processed = stored (Athena distinct count)"

REPORT_ENV = "S4_RUN_REPORT"
RUNS_DIR = REPO_ROOT / "runs"
COUNT_SQL = REPO_ROOT / "athena" / "count_events.sql"

TARGET_RATE = 500
TARGET_DURATION_S = 600
RATE_TOLERANCE = 0.95

DRAIN_TIMEOUT_S = 900  # the archiver waits up to 60 s per batch; give it plenty of room
ATHENA_TIMEOUT_S = 300
POLL_S = 15

_QUEUE_ATTRS = ["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"]


def run(ctx: Context, *, sleep: Callable[[float], None] = time.sleep) -> Measurement:
    path = report_path()
    report = _read_json(path)
    accepted = int(report["accepted"])
    start_ms, end_ms = int(report["start_ms"]), int(report["end_ms"])
    duration_s = (end_ms - start_ms) / 1000
    rate = float(report.get("achieved_rate") or report["sent"] / max(duration_s, 0.001))
    load_ok = duration_s >= TARGET_DURATION_S and rate >= TARGET_RATE * RATE_TOLERANCE

    queues = {"hot": ctx.cfg.hot_queue, "cold": ctx.cfg.cold_queue}
    drained, waited_s = wait_for_drain(ctx, queues.values(), sleep=sleep)
    dlq_depths = {name: queue_depth(ctx, name) for name in (ctx.cfg.processor_dlq, ctx.cfg.archiver_dlq)}
    dlqs_empty = not any(dlq_depths.values())

    total_rows, stored = count_stored(ctx, start_ms, end_ms + 1, sleep=sleep)
    metric = events_accepted_metric(ctx, start_ms, end_ms)
    lost = accepted - stored

    passed = load_ok and drained and dlqs_empty and stored == accepted
    measured = (
        f"{rate:.0f} ev/s for {duration_s:.0f} s; accepted {accepted:,}, "
        f"stored {stored:,} ({lost:,} lost); queues {'drained' if drained else 'NOT drained'}"
    )
    return Measurement(
        passed,
        measured,
        {
            "run_report": str(path),
            "run_id": report.get("run_id"),
            "load_target_met": load_ok,
            "duration_s": duration_s,
            "achieved_rate": rate,
            "sent": report.get("sent"),
            "accepted": accepted,
            "rejected_by_reason": report.get("rejected_by_reason", {}),
            "queues_drained": drained,
            "drain_wait_s": waited_s,
            "dlq_messages": dlq_depths,
            "stored_distinct": stored,
            "stored_rows": total_rows,
            "lost": lost,
            "events_accepted_metric": metric,
        },
    )


def report_path() -> Path:
    """The report named in ``S4_RUN_REPORT``, or the newest one in ``runs/``."""
    named = os.environ.get(REPORT_ENV)
    if named:
        return Path(named)
    reports = sorted(RUNS_DIR.glob("*.run-report.json"), key=lambda p: p.stat().st_mtime)
    if not reports:
        raise FileNotFoundError(
            f"No run report: run the simulator first, or set {REPORT_ENV}=<path to report>"
        )
    return reports[-1]


def queue_depth(ctx: Context, queue_name: str) -> int:
    sqs = ctx.client("sqs")
    url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=_QUEUE_ATTRS)["Attributes"]
    return sum(int(attrs.get(name, 0)) for name in _QUEUE_ATTRS)


def wait_for_drain(
    ctx: Context, queue_names: Any, *, sleep: Callable[[float], None] = time.sleep
) -> tuple[bool, float]:
    """Poll until every queue is empty (visible + in flight), up to ``DRAIN_TIMEOUT_S``."""
    names = list(queue_names)
    waited = 0.0
    while True:
        if all(queue_depth(ctx, name) == 0 for name in names):
            return True, waited
        if waited >= DRAIN_TIMEOUT_S:
            return False, waited
        sleep(POLL_S)
        waited += POLL_S


def count_stored(
    ctx: Context, start_ms: int, end_ms: int, *, sleep: Callable[[float], None] = time.sleep
) -> tuple[int, int]:
    """Run ``athena/count_events.sql`` (M5) on the window; returns (rows, distinct event_id)."""
    sql = "\n".join(
        line
        for line in COUNT_SQL.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ).strip()
    dt_from = _utc_date(start_ms)
    dt_to = _utc_date(end_ms) + timedelta(days=1)
    athena = ctx.client("athena")
    query_id = athena.start_query_execution(
        QueryString=sql,
        WorkGroup=ctx.cfg.athena_workgroup,
        QueryExecutionContext={"Database": ctx.cfg.glue_database},
        ExecutionParameters=[f"'{dt_from:%Y-%m-%d}'", f"'{dt_to:%Y-%m-%d}'", str(start_ms), str(end_ms)],
    )["QueryExecutionId"]
    waited = 0.0
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Athena query {state}: {status.get('StateChangeReason', '')}")
        if waited >= ATHENA_TIMEOUT_S:
            raise TimeoutError(f"Athena query {query_id} still {state} after {ATHENA_TIMEOUT_S} s")
        sleep(2)
        waited += 2
    rows = athena.get_query_results(QueryExecutionId=query_id)["ResultSet"]["Rows"]
    total, distinct = (int(cell["VarCharValue"]) for cell in rows[1]["Data"])
    return total, distinct


def events_accepted_metric(ctx: Context, start_ms: int, end_ms: int) -> float:
    """Sum of ``EventsAccepted`` (M3 ingest, §10) over the run, a minute of margin each side."""
    response = ctx.client("cloudwatch").get_metric_data(
        MetricDataQueries=[
            {
                "Id": "accepted",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "Earshot",
                        "MetricName": "EventsAccepted",
                        "Dimensions": [{"Name": "Stage", "Value": ctx.stage}],
                    },
                    "Period": 60,
                    "Stat": "Sum",
                },
                "ReturnData": True,
            }
        ],
        StartTime=_utc(start_ms) - timedelta(minutes=1),
        EndTime=_utc(end_ms) + timedelta(minutes=1),
    )
    return sum(sum(r.get("Values", [])) for r in response.get("MetricDataResults", []))


def _read_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _utc_date(ms: int) -> datetime:
    return _utc(ms).replace(hour=0, minute=0, second=0, microsecond=0)

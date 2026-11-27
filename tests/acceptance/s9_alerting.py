"""S9 · Quality alerting.

Owner: M4 + M3 · Spec: CONTEXT §14 S9, §8.2 (QoE), §11 (``--mode buffer-storm``).
Test method: send 120 distinct buffer events through ``POST /events`` for one region and
poll ``QoEAlertsSent`` for up to 2 minutes. The email is partly manual: record its arrival
time by hand in docs/results.md. Confirm the email arrives < 2 minutes after the storm.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

EVENT_COUNT = 120
BATCH_SIZE = 25
ALERT_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 5
REGION = "us-west"

CRITERION = "S9"
TITLE = "Quality alerting"
OWNER = "M4 + M3"
TARGET = "Buffer storm in one region → SNS email < 2 min"


def run(ctx: Context) -> Measurement:
    sample_path = Path(__file__).resolve().parents[2] / "contracts" / "samples" / "events.jsonl"
    with sample_path.open(encoding="utf-8") as sample_file:
        sample = json.loads(next(sample_file))

    client_ts = time.time_ns() // 1_000_000
    session_id = str(uuid.uuid4())
    events = []
    for index in range(EVENT_COUNT):
        event = dict(sample)
        event.pop("server_ts", None)
        event.update(
            event_id=str(uuid.uuid4()),
            user_id="sim-acceptance-s9",
            session_id=session_id,
            event_type="buffer",
            client_ts=client_ts + index,
            region=REGION,
            device="sim",
        )
        events.append(event)

    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    metric_start = started_at - timedelta(minutes=5)
    baseline = _qoe_alert_total(ctx, metric_start, started_at)

    accepted = 0
    for offset in range(0, len(events), BATCH_SIZE):
        batch = events[offset : offset + BATCH_SIZE]
        response = ctx.api.post("/events", {"events": batch})
        body = response.body
        if response.status != 202 or not isinstance(body, dict):
            return Measurement(
                False,
                f"event batch failed with HTTP {response.status}",
                {"accepted": accepted, "events": EVENT_COUNT, "region": REGION},
            )
        accepted += body.get("accepted", 0)
        if body.get("accepted") != len(batch) or body.get("rejected"):
            return Measurement(
                False,
                f"ingest accepted {accepted}/{EVENT_COUNT} buffer events",
                {"accepted": accepted, "events": EVENT_COUNT, "region": REGION},
            )

    while time.monotonic() - started < ALERT_TIMEOUT_SECONDS:
        metric_total = _qoe_alert_total(ctx, metric_start, datetime.now(timezone.utc))
        elapsed = round(time.monotonic() - started, 1)
        if metric_total > baseline:
            return Measurement(
                elapsed < ALERT_TIMEOUT_SECONDS,
                f"QoEAlertsSent increased by {metric_total - baseline} in {elapsed} s",
                {
                    "accepted": accepted,
                    "events": EVENT_COUNT,
                    "region": REGION,
                    "metric_baseline": baseline,
                    "metric_total": metric_total,
                    "metric_latency_sec": elapsed,
                    "email_arrival": "confirm manually in the subscribed inbox",
                },
            )
        time.sleep(POLL_INTERVAL_SECONDS)

    return Measurement(
        False,
        f"no QoEAlertsSent increase within {ALERT_TIMEOUT_SECONDS} s",
        {
            "accepted": accepted,
            "events": EVENT_COUNT,
            "region": REGION,
            "metric_baseline": baseline,
            "email_arrival": "not verified",
        },
    )


def _qoe_alert_total(ctx: Context, start: datetime, end: datetime) -> float:
    response = ctx.client("cloudwatch").get_metric_data(
        MetricDataQueries=[
            {
                "Id": "qoe_alerts",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "Earshot",
                        "MetricName": "QoEAlertsSent",
                        "Dimensions": [{"Name": "Stage", "Value": ctx.stage}],
                    },
                    "Period": 60,
                    "Stat": "Sum",
                },
                "ReturnData": True,
            }
        ],
        StartTime=start,
        EndTime=end,
    )
    results = response.get("MetricDataResults", [])
    return sum(sum(result.get("Values", [])) for result in results)

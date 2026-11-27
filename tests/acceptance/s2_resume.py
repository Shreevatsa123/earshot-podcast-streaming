"""S2 · Resume freshness and accuracy.

Owner: M4 + M1 · Spec: CONTEXT §14 S2, §8.2 (progress writes).
Test method: 20 timed trials. Send a ``pause`` event for a sim user (``ctx.api.post``),
then poll ``GET /progress/{episodeId}`` until the position appears. Pass if the p95 delay
is under 5 s and every stored position is within ±2 s of the one sent.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from acceptance.harness import Measurement

if TYPE_CHECKING:
    from acceptance.context import Context

TRIAL_COUNT = 20
POLL_INTERVAL_SECONDS = 0.1
TRIAL_TIMEOUT_SECONDS = 10
POSITION_TOLERANCE_SECONDS = 2
FRESHNESS_TARGET_MS = 5_000

CRITERION = "S2"
TITLE = "Resume freshness and accuracy"
OWNER = "M4 + M1"
TARGET = "Visible in API < 5 s after pause (p95 of 20 trials); resume within ±2 s"


def _p95(values: list[float]) -> float:
    """Return the nearest-rank 95th percentile."""
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _progress_visible(ctx: Context, user_id: str, episode_id: str) -> dict[str, Any] | None:
    response = ctx.api.get(f"/progress/{episode_id}", sim_user=user_id)
    body = response.body
    if (
        response.status == 200
        and isinstance(body, dict)
        and body.get("episode_id") == episode_id
        and body.get("updated_at") is not None
    ):
        return body
    return None


def run(ctx: Context) -> Measurement:
    sample_path = Path(__file__).resolve().parents[2] / "contracts" / "samples" / "events.jsonl"
    with sample_path.open(encoding="utf-8") as sample_file:
        sample = json.loads(next(sample_file))

    run_id = uuid.uuid4().hex[:12]
    latencies_ms = []
    position_mismatches = []

    for trial in range(TRIAL_COUNT):
        user_id = f"sim-s2-{run_id}-{trial:02d}"
        duration_sec = sample["duration_sec"]
        position_sec = min(600 + trial, duration_sec - 1) if duration_sec > 1 else 0
        event = dict(sample)
        event.pop("server_ts", None)
        event.update(
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            event_type="pause",
            position_sec=position_sec,
            client_ts=time.time_ns() // 1_000_000,
            device="sim",
        )

        started = time.monotonic()
        published = ctx.api.post("/events", {"events": [event]})
        if (
            published.status != 202
            or not isinstance(published.body, dict)
            or published.body.get("accepted") != 1
            or published.body.get("rejected")
        ):
            return Measurement(
                False,
                f"ingest did not accept the pause event in trial {trial + 1}",
                {
                    "run_id": run_id,
                    "completed_trials": len(latencies_ms),
                    "trial": trial + 1,
                    "status": published.status,
                    "response": published.body,
                },
            )

        deadline = started + TRIAL_TIMEOUT_SECONDS
        progress = None
        while time.monotonic() < deadline:
            progress = _progress_visible(ctx, user_id, event["episode_id"])
            if progress is not None:
                break
            time.sleep(POLL_INTERVAL_SECONDS)

        if progress is None:
            return Measurement(
                False,
                f"progress was not visible within {TRIAL_TIMEOUT_SECONDS} s in trial {trial + 1}",
                {
                    "run_id": run_id,
                    "completed_trials": len(latencies_ms),
                    "trial": trial + 1,
                    "latencies_ms": latencies_ms,
                },
            )

        latencies_ms.append(round((time.monotonic() - started) * 1000, 1))
        actual_position = progress.get("position_sec")
        if (
            type(actual_position) is not int
            or abs(actual_position - position_sec) > POSITION_TOLERANCE_SECONDS
        ):
            position_mismatches.append(
                {
                    "trial": trial + 1,
                    "expected_sec": position_sec,
                    "actual_sec": actual_position,
                }
            )

    p95_ms = _p95(latencies_ms)
    passed = p95_ms < FRESHNESS_TARGET_MS and not position_mismatches
    return Measurement(
        passed,
        f"p95 {p95_ms:.1f} ms; {len(position_mismatches)}/{TRIAL_COUNT} positions outside ±2 s",
        {
            "run_id": run_id,
            "trials": TRIAL_COUNT,
            "p95_ms": p95_ms,
            "latencies_ms": latencies_ms,
            "position_mismatches": position_mismatches,
        },
    )

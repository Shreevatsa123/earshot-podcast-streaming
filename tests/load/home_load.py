"""Helpers for the S6 ``/home`` load test (owner: M6 · tracker M6-06 · CONTEXT §14 S6).

Kept apart from ``locustfile.py`` so they can be unit-tested without Locust installed.
Stdlib only, plus ``shared.names`` for the SSM parameter names (CONTEXT §9).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from shared import names

#: The sim users the simulator creates by default (``simulator run --users 2000``), so most
#: of them have progress and some have recs.
SIM_USERS = 2000


@dataclass(frozen=True)
class Settings:
    api_url: str
    client_id: str
    password: str


def load_settings(ssm: Any, stage: str) -> Settings:
    """API URL, sim client id and sim-bot password for ``stage``, from SSM (CONTEXT §9)."""

    def value(name: str, decrypt: bool = False) -> str:
        return ssm.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]

    return Settings(
        api_url=value(names.ssm_api_url(stage)).rstrip("/"),
        client_id=value(names.ssm_sim_client_id(stage)),
        password=value(names.ssm_sim_password(stage), decrypt=True),
    )


def sim_user(rng: random.Random, users: int = SIM_USERS) -> str:
    """A random simulator user id, e.g. ``sim-000042`` (CONTEXT §7.2)."""
    return f"sim-{rng.randrange(users):06d}"


def home_headers(token: str, user: str) -> dict[str, str]:
    """Headers for ``GET /home`` acting as ``user`` (the sim client may do this, §7.2)."""
    return {"authorization": f"Bearer {token}", "x-earshot-sim-user": user, "accept": "application/json"}


# ---- Reading Locust's results (``--csv s6`` writes ``s6_stats.csv``) ----------------------

P95_LIMIT_MS = 500
ERROR_RATE_LIMIT_PCT = 1.0


@dataclass(frozen=True)
class LoadResult:
    requests: int
    failures: int
    p95_ms: float

    @property
    def error_rate_pct(self) -> float:
        return 100 * self.failures / self.requests if self.requests else 100.0

    @property
    def passed(self) -> bool:
        return self.requests > 0 and self.p95_ms < P95_LIMIT_MS and self.error_rate_pct < ERROR_RATE_LIMIT_PCT

    def summary(self) -> str:
        return (
            f"p95 {self.p95_ms:.0f} ms, errors {self.error_rate_pct:.2f} % "
            f"({self.failures}/{self.requests} requests)"
        )


def parse_stats(text: str) -> LoadResult:
    """The ``Aggregated`` row of Locust's ``*_stats.csv`` (falls back to the ``/home`` row)."""
    import csv
    import io

    rows = {row.get("Name", ""): row for row in csv.DictReader(io.StringIO(text.strip()))}
    row = rows.get("Aggregated") or rows.get("/home")
    if row is None:
        raise ValueError("No 'Aggregated' or '/home' row: is this Locust's s6_stats.csv?")
    p95 = row.get("95%", "")
    return LoadResult(
        requests=int(row["Request Count"]),
        failures=int(row["Failure Count"]),
        p95_ms=float(p95) if p95 not in ("", "N/A") else float("inf"),
    )

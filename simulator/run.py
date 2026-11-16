"""``simulator run``: real traffic through ``POST /events`` (CONTEXT §11, success criteria S4, S9).

- Logs in as ``sim-bot`` through the ``sim`` app client (USER_PASSWORD_AUTH) and refreshes
  the token 5 minutes before it expires.
- Sends batches of 25 events at ``--rate`` events/s for ``--duration`` s, on a thread pool.
  Each event is stamped with the current time; a batch mixes many virtual users, which
  the ``simulator`` group is allowed to do (§7.2).
- Retries only ``THROTTLED`` events, and whole batches that got HTTP 429/5xx or a network
  error: 3 retries with exponential backoff. A 401 refreshes the token first.
- ``--mode buffer-storm``: on top of the normal traffic, ``--storm-rate`` buffer events/s
  (default 3/s = 180/min, above the 100/min the spec asks for) in ``--storm-region``.
- At the end writes the run report (``runs/<run_id>.run-report.json`` by default, git-ignored):
  ``{"run_id","start_ms","end_ms","sent","accepted","rejected_by_reason",...}``.
"""

from __future__ import annotations

import json
import random
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Protocol

from simulator.model import Population

BATCH_SIZE = 25
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = (0.2, 0.4, 0.8)
TOKEN_REFRESH_MARGIN_SEC = 300
HTTP_TIMEOUT_SEC = 10
DEFAULT_STORM_RATE = 3.0


# ---- talking to AWS -------------------------------------------------------------------


class TokenProvider:
    """Cognito access token for ``sim-bot``, refreshed before expiry. Thread-safe."""

    def __init__(self, cognito: Any, client_id: str, username: str, password: str) -> None:
        self._cognito = cognito
        self._client_id = client_id
        self._username = username
        self._password = password
        self._lock = threading.Lock()
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at = 0.0

    def _store(self, result: dict[str, Any]) -> None:
        self._token = result["AccessToken"]
        self._refresh_token = result.get("RefreshToken", self._refresh_token)
        self._expires_at = time.time() + int(result.get("ExpiresIn", 3600))

    def _login(self) -> None:
        response = self._cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=self._client_id,
            AuthParameters={"USERNAME": self._username, "PASSWORD": self._password},
        )
        self._store(response["AuthenticationResult"])

    def _refresh(self) -> None:
        try:
            response = self._cognito.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self._client_id,
                AuthParameters={"REFRESH_TOKEN": self._refresh_token},
            )
            self._store(response["AuthenticationResult"])
        except Exception:  # noqa: BLE001 - refresh token expired or revoked: log in again
            self._login()

    def get(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            if self._token is None:
                self._login()
            elif force_refresh or time.time() > self._expires_at - TOKEN_REFRESH_MARGIN_SEC:
                if self._refresh_token:
                    self._refresh()
                else:
                    self._login()
            assert self._token is not None
            return self._token


class EventsApi(Protocol):
    def post(self, token: str, events: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]: ...


class HttpEventsApi:
    """``POST {api_url}/events`` with urllib (stdlib only)."""

    def __init__(self, api_url: str) -> None:
        self.url = api_url.rstrip("/") + "/events"

    def post(self, token: str, events: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps({"events": events}, separators=(",", ":")).encode(),
            method="POST",
            headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SEC) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            try:
                body = json.loads(error.read() or b"{}")
            except ValueError:
                body = {}
            return error.code, body
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return 0, {}


# ---- sending one batch ----------------------------------------------------------------


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sent = 0
        self.accepted = 0
        self.rejected: Counter[str] = Counter()
        self.requests = 0
        self.retries = 0

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "sent": self.sent,
                "accepted": self.accepted,
                "rejected_by_reason": dict(sorted(self.rejected.items())),
                "requests": self.requests,
                "retries": self.retries,
            }


def send_batch(
    api: EventsApi,
    tokens: Callable[..., str],
    events: list[dict[str, Any]],
    stats: Stats,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Send one batch, retrying per the §6 client rules, and record the outcome."""
    with stats.lock:
        stats.sent += len(events)
    pending = events
    final_rejects: Counter[str] = Counter()
    force_refresh = False
    for attempt in range(MAX_RETRIES + 1):
        status, body = api.post(tokens(force_refresh=force_refresh), pending)
        force_refresh = False
        with stats.lock:
            stats.requests += 1
            if attempt:
                stats.retries += 1
        if status == 202:
            retry: list[dict[str, Any]] = []
            for item in body.get("rejected", []):
                index, reason = item.get("index"), item.get("reason", "UNKNOWN")
                if reason == "THROTTLED" and isinstance(index, int) and 0 <= index < len(pending):
                    retry.append(pending[index])
                else:
                    final_rejects[reason] += 1
            with stats.lock:
                stats.accepted += int(body.get("accepted", 0))
            pending = retry
        elif status == 401:
            force_refresh = True
        elif status == 429 or status == 0 or status >= 500:
            pass  # retry the whole batch
        else:
            reason = (body.get("error") or {}).get("code") or f"HTTP_{status}"
            final_rejects[reason] += len(pending)
            pending = []
        if not pending:
            break
        if attempt < MAX_RETRIES:
            sleep(RETRY_BACKOFF_SEC[attempt])
    if pending:
        # Out of retries: record why the last attempt failed.
        if status == 202:
            final_rejects["THROTTLED"] += len(pending)
        else:
            final_rejects["NETWORK_ERROR" if status == 0 else f"HTTP_{status}"] += len(pending)
    with stats.lock:
        stats.rejected.update(final_rejects)


# ---- the run loop ---------------------------------------------------------------------


def new_run_id(rng: random.Random) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{stamp}-{rng.randrange(16**4):04x}"


def run(
    population: Population,
    *,
    api: EventsApi,
    tokens: Callable[..., str],
    rate: float,
    duration_sec: float,
    mode: str = "normal",
    storm_region: str = "us-west",
    storm_rate: float = DEFAULT_STORM_RATE,
    workers: int = 16,
    now_ms: Callable[[], int] = lambda: time.time_ns() // 1_000_000,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    progress_every_sec: float = 10.0,
) -> dict[str, Any]:
    """Send traffic for ``duration_sec`` and return the run report."""
    if rate <= 0 or duration_sec <= 0:
        raise ValueError("--rate and --duration must be positive")
    if mode not in ("normal", "buffer-storm"):
        raise ValueError("--mode must be normal or buffer-storm")
    rng = population.rng
    run_id = new_run_id(rng)
    stats = Stats()
    storm_users = [u for u in population.users if u.region == storm_region] or population.users
    interval = BATCH_SIZE / rate
    in_flight = threading.BoundedSemaphore(workers * 2)

    def task(batch: list[dict[str, Any]]) -> None:
        try:
            send_batch(api, tokens, batch, stats, sleep=sleep)
        finally:
            in_flight.release()

    start_ms = now_ms()
    t0 = monotonic()
    next_send = t0
    next_progress = t0 + progress_every_sec
    storm_sent = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sender") as pool:
        while True:
            now = monotonic()
            elapsed = now - t0
            if elapsed >= duration_sec:
                break
            if now < next_send:
                sleep(min(next_send - now, 0.05))
                continue
            client_ts = now_ms()
            batch = [population.step(rng.choice(population.users), client_ts)[0] for _ in range(BATCH_SIZE)]
            if mode == "buffer-storm":
                due = int(storm_rate * elapsed) - storm_sent
                for _ in range(max(0, due)):
                    batch.append(population.buffer_event(rng.choice(storm_users), client_ts, storm_region))
                storm_sent += max(0, due)
            for start in range(0, len(batch), BATCH_SIZE):
                in_flight.acquire()  # back-pressure: if the API is slow, the rate drops
                pool.submit(task, batch[start : start + BATCH_SIZE])
            next_send += interval
            if now >= next_progress:
                snap = stats.snapshot()
                print(
                    f"[{elapsed:6.0f}s] sent={snap['sent']} accepted={snap['accepted']} "
                    f"rejected={sum(snap['rejected_by_reason'].values())}",
                    flush=True,
                )
                next_progress += progress_every_sec

    end_ms = now_ms()
    snap = stats.snapshot()
    seconds = max((end_ms - start_ms) / 1000, 0.001)
    return {
        "run_id": run_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "sent": snap["sent"],
        "accepted": snap["accepted"],
        "rejected_by_reason": snap["rejected_by_reason"],
        "mode": mode,
        "users": len(population.users),
        "target_rate": rate,
        "achieved_rate": round(snap["sent"] / seconds, 1),
        "storm_region": storm_region if mode == "buffer-storm" else None,
        "storm_events": storm_sent,
        "requests": snap["requests"],
        "retries": snap["retries"],
    }

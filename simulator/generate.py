"""``simulator generate``: write events to a JSON Lines file, no AWS needed (CONTEXT §11).

The files are the fixtures M4 and M5 build and test with (e.g. the S3 test: 10k shuffled
events with 10 % duplicates).

- ``--events N`` is the number of **lines**. ``round(N * dup_rate)`` of them are
  duplicates (same ``event_id``, a later ``server_ts``, as a client retry would produce);
  the rest are unique.
- Events look like they already went through ingest: ``user_id`` (``sim-…``),
  ``server_ts`` (``client_ts`` + 30–1500 ms) and ``schema_version`` are set.
- Without ``--shuffle`` lines are in ``server_ts`` order; with it, in random order.
"""

from __future__ import annotations

import heapq
import json
import random
from pathlib import Path
from typing import Any

from shared.validate import order_fields

from simulator.model import Catalog, Population

DEFAULT_WINDOW_MS = 24 * 3600 * 1000


def generate_events(
    catalog: Catalog,
    *,
    users: int,
    events: int,
    seed: int,
    start_ms: int,
    window_ms: int = DEFAULT_WINDOW_MS,
    shuffle: bool = False,
    dup_rate: float = 0.0,
) -> list[dict[str, Any]]:
    """Generate ``events`` events (duplicates included) from ``users`` virtual users."""
    if events < 1:
        raise ValueError("--events must be at least 1")
    if not 0.0 <= dup_rate < 1.0:
        raise ValueError("--dup-rate must be in [0, 1)")
    rng = random.Random(seed)
    population = Population(catalog, users, rng)
    n_dups = round(events * dup_rate)
    n_unique = events - n_dups

    # Each user's next event time; always take the earliest, so a user's events are in
    # time order and their listening state stays consistent.
    queue = [(start_ms + int(rng.random() * window_ms), index) for index in range(users)]
    heapq.heapify(queue)
    unique: list[dict[str, Any]] = []
    while len(unique) < n_unique:
        client_ts, index = heapq.heappop(queue)
        event, wait_sec = population.step(population.users[index], client_ts)
        event["server_ts"] = client_ts + rng.randint(30, 1500)
        unique.append(order_fields(event))
        heapq.heappush(queue, (client_ts + int(wait_sec * 1000) + rng.randint(0, 999), index))

    duplicates = []
    for original in rng.choices(unique, k=n_dups) if n_dups else []:
        copy = dict(original)
        copy["server_ts"] = original["server_ts"] + rng.randint(100, 60_000)
        duplicates.append(copy)

    lines = unique + duplicates
    if shuffle:
        rng.shuffle(lines)
    else:
        lines.sort(key=lambda e: e["server_ts"])
    return lines


def write_jsonl(path: str | Path, events: list[dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as out:
        for event in events:
            out.write(json.dumps(event, separators=(",", ":")) + "\n")


def read_jsonl(path: str | Path) -> list[Any]:
    """Every line of a JSON Lines file (blank lines skipped). Bad JSON raises ``ValueError``."""
    events = []
    with open(path, encoding="utf-8") as src:
        for number, line in enumerate(src, start=1):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(f"{path}:{number}: not JSON ({error})") from error
    return events

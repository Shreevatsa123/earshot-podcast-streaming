"""M3-04: the committed sample events (contracts/samples/events.jsonl) follow CONTEXT §6."""

import json
from collections import Counter
from pathlib import Path

from shared.validate import EVENT_FIELDS, validate_event

ROOT = Path(__file__).resolve().parents[2]
LATER = 1_800_000_000_000  # any "now" after the fixture was generated


def load():
    lines = (ROOT / "contracts" / "samples" / "events.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_fixture_is_valid_and_enriched():
    events = load()
    assert len(events) == 1000
    for event in events:
        assert list(event) == list(EVENT_FIELDS)
        assert validate_event(event, now_ms=LATER)[1] is None
        assert event["user_id"].startswith("sim-") and event["server_ts"] >= event["client_ts"]


def test_fixture_uses_catalog_ids():
    catalog = json.loads((ROOT / "contracts" / "samples" / "catalog.json").read_text())
    known = {(e["show_id"], e["episode_id"], e["genre"], e["duration_sec"]) for e in catalog["episodes"]}
    for event in load():
        assert (event["show_id"], event["episode_id"], event["genre"], event["duration_sec"]) in known


def test_fixture_has_duplicates():
    counts = Counter(e["event_id"] for e in load())
    assert len(counts) == 950 and sum(n - 1 for n in counts.values()) == 50

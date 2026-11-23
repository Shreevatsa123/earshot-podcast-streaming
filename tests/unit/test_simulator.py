"""M3-05: simulator generate and replay (CONTEXT §11). No AWS."""

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.validate import EVENT_FIELDS, validate_event  # noqa: E402

from simulator import DEFAULT_CATALOG  # noqa: E402
from simulator.__main__ import main as cli  # noqa: E402
from simulator.generate import generate_events, read_jsonl  # noqa: E402
from simulator.model import Catalog  # noqa: E402
from simulator.replay import replay  # noqa: E402

START = 1_794_000_000_000
LATER = START + 30 * 24 * 3600 * 1000


@pytest.fixture(scope="module")
def catalog():
    return Catalog.load(DEFAULT_CATALOG)


@pytest.fixture(scope="module")
def catalog_ids():
    data = json.loads(DEFAULT_CATALOG.read_text())
    return {(e["show_id"], e["episode_id"], e["genre"], e["duration_sec"]) for e in data["episodes"]}


# ---- generate ---------------------------------------------------------------------------


def test_generate_is_valid_and_uses_catalog_ids(catalog, catalog_ids):
    events = generate_events(catalog, users=50, events=2000, seed=1, start_ms=START)
    assert len(events) == 2000
    for e in events:
        assert list(e) == list(EVENT_FIELDS)
        assert validate_event(e, now_ms=LATER)[1] is None
        assert e["user_id"].startswith("sim-") and e["device"] == "sim"
        assert e["server_ts"] >= e["client_ts"]
        assert (e["show_id"], e["episode_id"], e["genre"], e["duration_sec"]) in catalog_ids
    assert [e["server_ts"] for e in events] == sorted(e["server_ts"] for e in events)


def test_generate_is_deterministic(catalog):
    a = generate_events(catalog, users=20, events=300, seed=9, start_ms=START, shuffle=True, dup_rate=0.1)
    b = generate_events(catalog, users=20, events=300, seed=9, start_ms=START, shuffle=True, dup_rate=0.1)
    assert a == b


def test_generate_duplicates_and_shuffle(catalog):
    events = generate_events(catalog, users=100, events=10_000, seed=7, start_ms=START, shuffle=True, dup_rate=0.10)
    ids = Counter(e["event_id"] for e in events)
    assert len(events) == 10_000
    assert len(ids) == 9_000
    assert sum(n - 1 for n in ids.values()) == 1_000
    assert [e["server_ts"] for e in events] != sorted(e["server_ts"] for e in events)


def test_sessions_are_consistent_per_user(catalog):
    """Within a session: one play first, positions never exceed the duration, ends at most once."""
    events = generate_events(catalog, users=30, events=3000, seed=3, start_ms=START)
    sessions = {}
    for e in sorted(events, key=lambda e: e["client_ts"]):
        sessions.setdefault(e["session_id"], []).append(e)
    for evs in sessions.values():
        assert evs[0]["event_type"] == "play"
        assert len({(e["user_id"], e["episode_id"]) for e in evs}) == 1
        assert all(0 <= e["position_sec"] <= e["duration_sec"] for e in evs)
        ends = [e for e in evs if e["event_type"] in ("pause", "complete")]
        assert len(ends) <= 1 and (not ends or ends[0] is evs[-1])


def test_traffic_has_every_event_type_and_popular_episodes(catalog):
    events = generate_events(catalog, users=200, events=10_000, seed=7, start_ms=START)
    assert set(Counter(e["event_type"] for e in events)) == {"play", "pause", "seek", "buffer", "heartbeat", "complete"}
    plays = Counter(e["episode_id"] for e in events if e["event_type"] == "play")
    top = plays.most_common(1)[0][1]
    assert top >= 5 * (sum(plays.values()) / len(plays))  # Zipf: clear trending winners


def test_cli_generate(tmp_path):
    out = tmp_path / "e.jsonl"
    assert cli(["generate", "--out", str(out), "--users", "10", "--events", "100", "--start", "2026-11-14"]) == 0
    assert len(read_jsonl(out)) == 100


# ---- replay -----------------------------------------------------------------------------


class FakeSns:
    def __init__(self, fail_first_ids=()):
        self.fail = set(fail_first_ids)
        self.calls = []

    def publish_batch(self, TopicArn, PublishBatchRequestEntries):  # noqa: N803
        self.calls.append(PublishBatchRequestEntries)
        ok, failed = [], []
        for entry in PublishBatchRequestEntries:
            if entry["Id"] in self.fail:
                self.fail.discard(entry["Id"])
                failed.append({"Id": entry["Id"], "Code": "Throttled", "SenderFault": False})
            else:
                ok.append({"Id": entry["Id"], "MessageId": "x"})
        return {"Successful": ok, "Failed": failed}


def test_replay_publishes_25_per_message(catalog):
    events = generate_events(catalog, users=10, events=260, seed=2, start_ms=START, dup_rate=0.1)
    sns = FakeSns(fail_first_ids={"m3"})
    report = replay(events + [{"bad": 1}], sns=sns, topic_arn="arn:t", now_fn=lambda: LATER, sleep=lambda s: None)
    assert report["messages"] == 11  # 260 / 25 rounded up
    assert report["published_events"] == 260
    assert report["skipped_invalid"] == 1
    assert report["failed_messages"] == 0
    assert len(sns.calls[0]) == 10  # PublishBatch takes 10 messages per call
    bodies = [json.loads(entry["Message"]) for call in sns.calls for entry in call]
    assert all(e["server_ts"] == LATER for body in bodies for e in body["events"])


def test_replay_can_keep_server_ts(catalog):
    events = generate_events(catalog, users=5, events=30, seed=2, start_ms=START)
    sns = FakeSns()
    replay(events, sns=sns, topic_arn="arn:t", keep_server_ts=True, now_fn=lambda: LATER)
    sent = [e for call in sns.calls for entry in call for e in json.loads(entry["Message"])["events"]]
    assert [e["server_ts"] for e in sent] == [e["server_ts"] for e in events]

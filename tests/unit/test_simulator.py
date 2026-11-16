"""M3-04/05/06/08: simulator generate, replay, run and buffer-storm (CONTEXT §11). No AWS."""

import json
import random
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
from simulator.model import Catalog, Population  # noqa: E402
from simulator.replay import replay  # noqa: E402
from simulator.run import Stats, run, send_batch  # noqa: E402

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


def test_committed_fixture_is_valid():
    events = read_jsonl(ROOT / "contracts" / "samples" / "events.jsonl")
    assert len(events) == 1000
    assert all(validate_event(e, now_ms=LATER)[1] is None for e in events)
    assert all(list(e) == list(EVENT_FIELDS) for e in events)


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


# ---- run --------------------------------------------------------------------------------


class FakeApi:
    """Accepts everything, except the first time it sees an event it can throttle it."""

    def __init__(self, throttle_first=False, statuses=()):
        self.throttle_first = throttle_first
        self.statuses = list(statuses)
        self.seen = set()
        self.received = []

    def post(self, token, events):
        if self.statuses:
            return self.statuses.pop(0), {}
        rejected = []
        for i, e in enumerate(events):
            if self.throttle_first and e["event_id"] not in self.seen:
                self.seen.add(e["event_id"])
                rejected.append({"index": i, "reason": "THROTTLED"})
            else:
                self.received.append(e)
        return 202, {"accepted": len(events) - len(rejected), "rejected": rejected}


def tokens(force_refresh=False):
    return "token"


def batch(catalog, n=25):
    pop = Population(catalog, 10, random.Random(1))
    return [pop.step(pop.users[i % 10], START)[0] for i in range(n)]


def test_send_batch_retries_throttled_only(catalog):
    api, stats = FakeApi(throttle_first=True), Stats()
    send_batch(api, tokens, batch(catalog), stats, sleep=lambda s: None)
    snap = stats.snapshot()
    assert (snap["sent"], snap["accepted"], snap["rejected_by_reason"]) == (25, 25, {})
    assert snap["retries"] == 1


def test_send_batch_gives_up_after_3_retries(catalog):
    api, stats = FakeApi(statuses=[503, 503, 503, 503]), Stats()
    send_batch(api, tokens, batch(catalog), stats, sleep=lambda s: None)
    assert stats.snapshot()["rejected_by_reason"] == {"HTTP_503": 25}
    assert stats.snapshot()["requests"] == 4


def test_send_batch_401_refreshes_token(catalog):
    calls = []

    def toks(force_refresh=False):
        calls.append(force_refresh)
        return "t"

    api, stats = FakeApi(statuses=[401]), Stats()
    send_batch(api, toks, batch(catalog), stats, sleep=lambda s: None)
    assert calls == [False, True]
    assert stats.snapshot()["accepted"] == 25


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(seconds, 0.001)

    def now_ms(self):
        return START + int(self.t * 1000)


def test_run_rate_and_report(catalog):
    clock, api = FakeClock(), FakeApi()
    pop = Population(catalog, 100, random.Random(42))
    report = run(
        pop, api=api, tokens=tokens, rate=500, duration_sec=10,
        now_ms=clock.now_ms, monotonic=clock.monotonic, sleep=clock.sleep,
    )  # fmt: skip
    assert report["sent"] == report["accepted"] == len(api.received)
    assert 4_900 <= report["sent"] <= 5_100  # 500/s for 10 s
    assert report["rejected_by_reason"] == {}
    for key in ("run_id", "start_ms", "end_ms", "sent", "accepted", "rejected_by_reason"):
        assert key in report
    assert all(e["user_id"].startswith("sim-") for e in api.received)


def test_buffer_storm_mode(catalog):
    clock, api = FakeClock(), FakeApi()
    pop = Population(catalog, 200, random.Random(42))
    report = run(
        pop, api=api, tokens=tokens, rate=50, duration_sec=60, mode="buffer-storm",
        storm_region="ap-south", storm_rate=3,
        now_ms=clock.now_ms, monotonic=clock.monotonic, sleep=clock.sleep,
    )  # fmt: skip
    storm = [e for e in api.received if e["event_type"] == "buffer" and e["region"] == "ap-south"]
    assert len(storm) >= 100  # ≥ 100 buffer events per minute in one region (§11)
    assert report["storm_events"] >= 170
    assert len({e["event_id"] for e in storm}) == len(storm)  # distinct, so QoE counts them all

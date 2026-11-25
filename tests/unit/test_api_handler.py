"""M2-05: the API Lambda's read routes (CONTEXT §7.3) against a moto table seeded with the
real catalog. Where an M2-07 sample exists, the route must return exactly that sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from api import handler
from shared.clock import utc_date

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "contracts" / "samples"
sys.path.insert(0, str(REPO / "scripts" / "catalog"))
import seed_catalog  # noqa: E402

CATALOG = json.loads((SAMPLES / "catalog.json").read_text(encoding="utf-8"))
NOW = 1_794_076_200_000  # 2026-11-07 18:30 UTC
TODAY = utc_date(NOW)


def sample(name: str):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


FLAGS_PARAM = "/earshot/test/flags"


def clear_caches():
    for cached in (handler._dynamodb, handler._fast_dynamodb, handler._ssm):
        getattr(cached, "cache_clear", lambda: None)()  # a test may have swapped one for a fake
    handler._flags_cache = (0, {})


def set_flags(**flags):
    """Write the flags parameter (moto) and drop the 10 s cache."""
    import boto3

    value = json.dumps({"recs_enabled": True, "recs_fault_injection": False, **flags})
    boto3.client("ssm", region_name="us-east-1").put_parameter(Name=FLAGS_PARAM, Value=value, Type="String", Overwrite=True)
    handler._flags_cache = (0, {})


@pytest.fixture
def table(ddb_table, monkeypatch):
    monkeypatch.setenv("TABLE_NAME", ddb_table.name)
    monkeypatch.setenv("FLAGS_PARAM", FLAGS_PARAM)
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setattr(handler, "now_ms", lambda: NOW)
    clear_caches()  # fresh clients inside moto
    seed_catalog.seed(ddb_table, CATALOG)
    set_flags()
    yield ddb_table
    clear_caches()


def call(route, *, path=None, query=None, sub="user-1", groups=None, headers=None):
    claims = {"sub": sub} if sub else {}
    if groups:
        claims["cognito:groups"] = groups
    event = {
        "routeKey": route,
        "pathParameters": path,
        "queryStringParameters": query,
        "headers": headers or {},
        "requestContext": {"authorizer": {"jwt": {"claims": claims}}},
    }
    response = handler.main(event, None)
    return response["statusCode"], json.loads(response["body"])


def test_health_and_genres(table):
    assert call("GET /health", sub=None) == (200, {"status": "ok", "stage": "test"})
    status, body = call("GET /genres")
    assert status == 200 and len(body["genres"]) == 8
    assert body["genres"][0] == {"id": "true-crime", "name": "True Crime"}


def test_shows_match_the_sample(table):
    assert call("GET /shows", query={"genre": "true-crime"}) == (200, sample("shows.json"))
    status, body = call("GET /shows", query={"genre": "true-crime", "limit": "2"})
    assert body["shows"] == sample("shows.json")["shows"][:2]


@pytest.mark.parametrize(
    "query", [None, {"genre": "jazz"}, {"genre": "news", "limit": "0"}, {"genre": "news", "limit": "51"}, {"genre": "news", "limit": "x"}]
)
def test_shows_rejects_bad_parameters(table, query):
    status, body = call("GET /shows", query=query)
    assert status == 400 and body["error"]["code"] == "BAD_REQUEST"


def test_show_detail_matches_the_sample_and_404s(table):
    assert call("GET /shows/{showId}", path={"showId": "7212041"}) == (200, sample("show_detail.json"))
    status, body = call("GET /shows/{showId}", path={"showId": "nope"})
    assert status == 404 and body["error"]["code"] == "NOT_FOUND"


def test_progress_defaults_and_stored_position(table):
    path = {"episodeId": "62885141741"}
    assert call("GET /progress/{episodeId}", path=path) == (
        200,
        {"episode_id": "62885141741", "position_sec": 0, "completed": False, "updated_at": None},
    )
    table.put_item(
        Item={"PK": "USER#user-1", "SK": "PROG#62885141741", "position_sec": 578, "completed": False, "updated_at": 7}
    )
    assert call("GET /progress/{episodeId}", path=path)[1]["position_sec"] == 578


def test_progress_identity_rules(table):
    """§7.2: only the simulator group may act as a sim-* user via the header."""
    path = {"episodeId": "e1"}
    table.put_item(Item={"PK": "USER#sim-000042", "SK": "PROG#e1", "position_sec": 9, "completed": True, "updated_at": 1})
    header = {"x-earshot-sim-user": "sim-000042"}

    assert call("GET /progress/{episodeId}", path=path, groups="[simulator]", headers=header)[1]["position_sec"] == 9
    assert call("GET /progress/{episodeId}", path=path, headers=header)[1]["position_sec"] == 0  # header ignored
    status, body = call("GET /progress/{episodeId}", path=path, groups="[simulator]", headers={"x-earshot-sim-user": "bob"})
    assert status == 403 and body["error"]["code"] == "FORBIDDEN"


def test_trending_counts_today_plays_descending(table):
    episodes = CATALOG["episodes"][:3]
    for episode, plays in zip(episodes, (5, 9, 1), strict=True):
        table.put_item(Item={"PK": f"TREND#{TODAY}", "SK": f"EP#{episode['episode_id']}", "show_id": episode["show_id"], "plays": plays})
    table.put_item(Item={"PK": f"TREND#{TODAY}", "SK": "EP#gone", "show_id": "gone", "plays": 50})  # not in the catalog
    table.put_item(Item={"PK": "TREND#2026-11-06", "SK": f"EP#{episodes[2]['episode_id']}", "show_id": "x", "plays": 99})

    status, body = call("GET /trending", query={"limit": "2"})
    assert status == 200 and body["date"] == TODAY
    assert [(i["episode_id"], i["plays"]) for i in body["items"]] == [
        (episodes[1]["episode_id"], 9),
        (episodes[0]["episode_id"], 5),
    ]
    first = body["items"][0]
    assert first["audio_url"] == episodes[1]["audio_url"] and first["show_title"] == CATALOG["shows"][0]["title"]
    assert len(call("GET /trending")[1]["items"]) == 3  # "gone" is skipped, yesterday is ignored


def test_unknown_route_and_unexpected_errors(table, monkeypatch):
    status, body = call("GET /nope")
    assert status == 404 and body["error"]["code"] == "NOT_FOUND"
    monkeypatch.delenv("TABLE_NAME")
    status, body = call("GET /shows", query={"genre": "news"})
    assert status == 500 and body == {"error": {"code": "INTERNAL", "message": "Something went wrong"}}


# ---- GET /home (M2-06, §7.4) ---------------------------------------------------------------

EPISODES = CATALOG["episodes"]
SHOWS = {show["show_id"]: show for show in CATALOG["shows"]}


def ref(episode, **extra):
    return {"show_id": episode["show_id"], "episode_id": episode["episode_id"], **extra}


def home(**kwargs):
    status, body = call("GET /home", **kwargs)
    assert status == 200, body
    return body, {row["id"]: row for row in body["rows"]}


def test_home_new_user_gets_the_featured_fallback(table):
    body, rows = home()
    assert body["user_id"] == "user-1" and body["generated_at"] == NOW and body["degraded"] is False
    assert list(rows) == ["popular"]  # no progress, no trending, no POPULAR, no RECS
    popular = rows["popular"]
    assert popular["title"] == "Popular on Earshot" and popular["source"] == "popular_fallback"
    assert [c["episode_id"] for c in popular["items"]] == [f["episode_id"] for f in CATALOG["featured"][:10]]


def test_home_continue_row_unfinished_newest_first(table):
    for episode, position, done, updated in ((EPISODES[0], 50, False, 1), (EPISODES[1], 70, False, 3), (EPISODES[2], 9, True, 5)):
        table.put_item(Item={"PK": "USER#user-1", "SK": f"PROG#{episode['episode_id']}", "show_id": episode["show_id"],
                             "episode_id": episode["episode_id"], "position_sec": position, "completed": done, "updated_at": updated})
    _, rows = home()
    row = rows["continue"]
    assert row["title"] == "Continue Listening" and row["source"] == "progress"
    assert [(c["episode_id"], c["position_sec"]) for c in row["items"]] == [(EPISODES[1]["episode_id"], 70), (EPISODES[0]["episode_id"], 50)]


def test_home_trending_is_filled_up_from_popular(table):
    table.put_item(Item={"PK": f"TREND#{TODAY}", "SK": f"EP#{EPISODES[0]['episode_id']}", "show_id": EPISODES[0]["show_id"], "plays": 4})
    popular = [ref(EPISODES[0], plays=40)] + [ref(e, plays=30 - n) for n, e in enumerate(EPISODES[10:15])]
    table.put_item(Item={"PK": "POPULAR", "SK": "GLOBAL", "items": popular})
    _, rows = home()
    items = rows["trending"]["items"]
    assert items[0] == {**items[0], "episode_id": EPISODES[0]["episode_id"], "plays": 4}  # today's count, not POPULAR's
    assert [c["episode_id"] for c in items[1:]] == [e["episode_id"] for e in EPISODES[10:15]]  # no repeat
    assert rows["popular"]["source"] == "popular_fallback"  # no RECS: POPULAR also feeds the fallback


def test_home_personalized_rows_replace_the_fallback(table):
    rec_rows = [
        {"seed_show_id": EPISODES[0]["show_id"], "seed_episode_id": EPISODES[0]["episode_id"],
         "items": [ref(e, score=9 - n) for n, e in enumerate(EPISODES[20:32])]},
        {"seed_show_id": EPISODES[40]["show_id"], "seed_episode_id": EPISODES[40]["episode_id"], "items": [ref(EPISODES[50], score=1)]},
    ]
    table.put_item(Item={"PK": "USER#user-1", "SK": "RECS", "rows": rec_rows, "generated_at": 1, "run_id": "r1"})
    body, rows = home()
    assert body["degraded"] is False and "popular" not in rows
    assert rows["recs-1"]["title"] == f"Because you listened to {EPISODES[0]['title']}"
    assert rows["recs-1"]["source"] == "personalized"
    assert [c["episode_id"] for c in rows["recs-1"]["items"]] == [e["episode_id"] for e in EPISODES[20:30]]  # capped at 10
    assert rows["recs-2"]["items"][0]["show_title"] == SHOWS[EPISODES[50]["show_id"]]["title"]


def test_home_recs_disabled_uses_the_fallback_without_degrading(table, capsys):
    table.put_item(Item={"PK": "USER#user-1", "SK": "RECS", "rows": [], "generated_at": 1, "run_id": "r1"})
    set_flags(recs_enabled=False)
    body, rows = home()
    assert body["degraded"] is False and "popular" in rows
    assert "HomeFallback" not in capsys.readouterr().out


def test_home_fault_injection_degrades_and_emits_the_metric(table, capsys):
    """S8: recs_enabled=false and recs_fault_injection=true → 200, degraded, fallback row."""
    set_flags(recs_enabled=False, recs_fault_injection=True)
    body, rows = home()
    assert body["degraded"] is True and rows["popular"]["source"] == "popular_fallback"
    assert '"HomeFallback": 1' in capsys.readouterr().out


def test_home_never_5xx_when_the_recs_lookup_fails(table, monkeypatch, capsys):
    class TimingOut:
        def Table(self, name):  # noqa: N802 (boto3's name)
            raise TimeoutError("read timeout after 0.3 s")

    monkeypatch.setattr(handler, "_fast_dynamodb", lambda: TimingOut())
    body, rows = home()
    assert body["degraded"] is True and "popular" in rows
    assert '"HomeFallback": 1' in capsys.readouterr().out


def test_home_acts_as_the_sim_user_for_the_simulator(table):
    episode = EPISODES[3]
    table.put_item(Item={"PK": "USER#sim-000042", "SK": f"PROG#{episode['episode_id']}", "show_id": episode["show_id"],
                         "episode_id": episode["episode_id"], "position_sec": 11, "completed": False, "updated_at": 1})
    body, rows = home(groups="[simulator]", headers={"x-earshot-sim-user": "sim-000042"})
    assert body["user_id"] == "sim-000042" and rows["continue"]["items"][0]["position_sec"] == 11


def test_flags_are_cached_for_10_seconds(table, monkeypatch):
    assert handler.get_flags()["recs_enabled"] is True
    set_flags(recs_enabled=False)
    handler._flags_cache = (NOW + 10_000, {"recs_enabled": True, "recs_fault_injection": False})  # read at NOW
    assert handler.get_flags()["recs_enabled"] is True  # still cached
    monkeypatch.setattr(handler, "now_ms", lambda: NOW + 10_001)
    assert handler.get_flags()["recs_enabled"] is False

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


def clear_caches():
    handler._dynamodb.cache_clear()


@pytest.fixture
def table(ddb_table, monkeypatch):
    monkeypatch.setenv("TABLE_NAME", ddb_table.name)
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setattr(handler, "now_ms", lambda: NOW)
    clear_caches()  # fresh clients inside moto
    seed_catalog.seed(ddb_table, CATALOG)
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


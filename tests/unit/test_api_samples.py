"""The M2-07 sample API responses match CONTEXT §7.3/§7.4 and the IDs in catalog.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "samples"
CARD = {"show_id", "episode_id", "title", "show_title", "image_url", "audio_url", "duration_sec", "genre"}
LIST_SHOW = {"show_id", "title", "author", "image_url", "genre", "episode_count"}
ROW_SOURCES = {"progress", "trending", "personalized", "popular_fallback"}


def load(name: str):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


CATALOG = load("catalog.json")
SHOWS = {show["show_id"]: show for show in CATALOG["shows"]}
EPISODES = {episode["episode_id"]: episode for episode in CATALOG["episodes"]}


def check_card(card: dict, extra: frozenset[str] = frozenset()) -> None:
    """An EpisodeCard (§7.1) whose values are hydrated from the catalog."""
    assert set(card) == CARD | extra
    episode = EPISODES[card["episode_id"]]
    for key in CARD - {"show_title"}:
        assert card[key] == episode[key], key
    assert card["show_title"] == SHOWS[card["show_id"]]["title"]


def test_shows_lists_one_genre_sorted_by_title():
    shows = load("shows.json")["shows"]
    assert len({show["genre"] for show in shows}) == 1
    assert [s["title"].lower() for s in shows] == sorted(s["title"].lower() for s in shows)
    for show in shows:
        assert set(show) == LIST_SHOW
        assert show == {key: SHOWS[show["show_id"]][key] for key in LIST_SHOW}


def test_show_detail_has_every_episode_newest_first():
    body = load("show_detail.json")
    show = body["show"]
    assert set(show) == LIST_SHOW | {"description"}
    assert show == {key: SHOWS[show["show_id"]][key] for key in LIST_SHOW | {"description"}}
    for card in body["episodes"]:
        check_card(card)
    published = [EPISODES[card["episode_id"]]["published_at"] for card in body["episodes"]]
    assert published == sorted(published, reverse=True)
    assert len(body["episodes"]) == show["episode_count"]


def test_progress_shape():
    progress = load("progress.json")
    assert set(progress) == {"episode_id", "position_sec", "completed", "updated_at"}
    assert 0 <= progress["position_sec"] <= EPISODES[progress["episode_id"]]["duration_sec"]
    assert type(progress["completed"]) is bool and type(progress["updated_at"]) is int


def test_trending_is_todays_plays_descending():
    body = load("trending.json")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", body["date"])
    assert 1 <= len(body["items"]) <= 20
    for card in body["items"]:
        check_card(card, frozenset({"plays"}))
    plays = [card["plays"] for card in body["items"]]
    assert plays == sorted(plays, reverse=True)


def test_home_rows_follow_the_rules():
    home = load("home.json")
    assert set(home) == {"user_id", "generated_at", "degraded", "rows"}
    assert home["rows"], "home always has at least one row (§7.4 rule 5)"
    for row in home["rows"]:
        assert set(row) == {"id", "title", "source", "items"} and row["source"] in ROW_SOURCES
        assert 1 <= len(row["items"]) <= 10
        extra = {"progress": {"position_sec"}, "trending": {"plays"}}.get(row["source"], set())
        for card in row["items"]:
            check_card(card, frozenset(extra))
        if row["source"] == "progress":  # unfinished only (§7.4 rule 1, §6 "completed")
            assert all(c["position_sec"] < 0.95 * c["duration_sec"] for c in row["items"])
        if row["source"] == "personalized":
            assert re.fullmatch(r"recs-[12]", row["id"]) and row["title"].startswith("Because you listened to ")

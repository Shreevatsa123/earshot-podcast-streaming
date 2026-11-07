"""Tests for scripts/catalog/fetch_catalog.py (M2-01), offline against a fake Podcast Index."""

from __future__ import annotations

import hashlib
import json

import pytest
from catalog import fetch_catalog as fc

from shared import names


def item(episode_id: int, published: int, **overrides):
    return {
        "id": episode_id,
        "title": f"Ep {episode_id}",
        "datePublished": published,
        "duration": 1800,
        "enclosureUrl": f"https://cdn.example/{episode_id}.mp3",
        "enclosureType": "audio/mpeg",
        "image": "",
        "feedImage": "https://img.example/feed.jpg",
        **overrides,
    }


def fake_api():
    """Every genre's trending list starts with show 1 (shared) and show 2 (too few episodes)."""
    categories = [{"id": 1, "name": "Arts"}]
    categories += [{"id": 10 + n, "name": label} for n, label in enumerate(names.GENRES.values())]

    def feed(feed_id: int):
        return {
            "id": feed_id,
            "title": f"Show {feed_id}",
            "author": "Author",
            "description": "<p>About &amp; more</p>",
            "artwork": f"https://img.example/{feed_id}.jpg",
        }

    def get(path, params):
        if path == "/categories/list":
            return {"feeds": categories}
        if path == "/podcasts/trending":
            genre_no = params["cat"] - 10
            return {"feeds": [feed(1), feed(2)] + [feed(1000 * (genre_no + 1) + i) for i in range(10)]}
        if path == "/episodes/byfeedid":
            count = 5 if params["id"] == 2 else 25
            return {"items": [item(params["id"] * 100 + i, 1_700_000_000 + i) for i in range(count)]}
        raise AssertionError(f"unexpected call {path}")

    return get


def test_auth_header_signs_key_secret_and_date():
    headers = fc.auth_headers("key", "secret", 1_700_000_000)
    assert headers["X-Auth-Date"] == "1700000000"
    assert headers["Authorization"] == hashlib.sha1(b"keysecret1700000000").hexdigest()


def test_clean_text_strips_html_and_truncates():
    assert fc.clean_text("<p>Tom &amp; Jerry</p>\n  show") == "Tom & Jerry show"
    assert fc.clean_text("abcdef", 4) == "abc…"
    assert fc.clean_text(None) == ""


def test_playable_episodes_keeps_newest_https_audio_with_duration():
    newest_but_broken = [
        item(100, 1_800_000_000, enclosureUrl="http://cdn.example/x.mp3"),
        item(101, 1_800_000_000, enclosureType="video/mp4"),
        item(102, 1_800_000_000, duration=0),
        item(103, 1_800_000_000, duration=None),
        item(104, 1_800_000_000, duration=90_000),
        item(105, 1_800_000_000, title="<b></b>"),
    ]
    picked = fc.playable_episodes([item(i, 1_700_000_000 + i) for i in range(30)] + newest_but_broken)
    assert [episode["id"] for episode in picked] == list(range(29, 9, -1))


def test_build_catalog_picks_six_shows_per_genre_once_each():
    catalog = fc.build_catalog(fake_api())
    assert fc.check_catalog(catalog) == []

    show_ids = [show["show_id"] for show in catalog["shows"]]
    assert len(show_ids) == 6 * len(names.GENRES)
    assert show_ids.count("1") == 1  # trending in every genre, kept under the first only
    assert "2" not in show_ids  # fewer than MIN_EPISODES playable episodes
    assert len(catalog["episodes"]) == 20 * len(show_ids)
    assert catalog["shows"][0]["description"] == "About & more"


def test_check_catalog_reports_contract_problems():
    catalog = fc.build_catalog(fake_api())
    catalog["episodes"][0]["audio_url"] = "http://insecure.example/a.mp3"
    catalog["episodes"][1]["episode_id"] = catalog["episodes"][2]["episode_id"]
    catalog["shows"] = [show for show in catalog["shows"] if show["genre"] != "history"]
    catalog["featured"] = [{"show_id": "1", "episode_id": "not-in-catalog"}]

    problems = "\n".join(fc.check_catalog(catalog))
    assert "isn't https" in problems
    assert "duplicate episode_id" in problems
    assert "no shows for genre history" in problems
    assert "featured must list 20 different episodes" in problems
    assert "not an episode in this catalog" in problems


def test_committed_catalog_matches_the_contract():
    if not fc.DEFAULT_OUT.exists():
        pytest.skip("contracts/samples/catalog.json isn't committed yet (M2-01)")
    catalog = json.loads(fc.DEFAULT_OUT.read_text(encoding="utf-8"))
    assert fc.check_catalog(catalog) == []
    assert len(catalog["featured"]) == fc.FEATURED_COUNT  # M2-02

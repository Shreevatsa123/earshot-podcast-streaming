#!/usr/bin/env python3
"""Build the catalog snapshot ``contracts/samples/catalog.json`` from the Podcast Index API.

Owner: M2 · Tracker: M2-01 · Spec: CONTEXT §8.1 (Show, Episode), §8.3 (genres), §9 (SSM keys)

Run it once and commit the output. Every account seeds from the committed file (M2-03), so
IDs match everywhere and nothing depends on Podcast Index at runtime::

    python scripts/catalog/fetch_catalog.py --stage <you>

The API key and secret are read from SecureString parameters in **your own** account
(CONTEXT §9). Create them once; ``read -rs`` keeps the values out of your shell history::

    read -rs PI_KEY; read -rs PI_SECRET
    aws ssm put-parameter --type SecureString --name /earshot/<you>/podcastindex/key --value "$PI_KEY"
    aws ssm put-parameter --type SecureString --name /earshot/<you>/podcastindex/secret --value "$PI_SECRET"

Output: two flat lists whose entries have exactly the §8.1 attributes (no table keys;
the seed script adds those)::

    {"source": "...", "generated_at": <epoch ms>,
     "shows":    [{show_id, title, author, description, image_url, genre, episode_count}],
     "episodes": [{show_id, episode_id, title, audio_url, duration_sec, published_at,
                   image_url, genre}]}

Selection: for each genre (§8.3), the top trending English shows in the Podcast Index
category of the same name, 6 per genre, each with its 20 newest playable episodes.
"Playable" means an https audio file (the site is served over https, so browsers block
http audio) and a duration of 1 s to 24 h (events need ``duration_sec > 0`` and
``position_sec <= 86400``). A show appears under one genre only. ``episode_count`` counts
the show's episodes in this snapshot.

The committed file also has ``"featured": [{show_id, episode_id}]``: the 20 hand-picked,
verified-playable episodes for the FEATURED item (M2-02). This script doesn't write it, so
a re-run drops it: pick again and verify with ``check_featured.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "services") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "services"))

from shared import names  # noqa: E402
from shared.clock import now_ms  # noqa: E402

API_BASE = "https://api.podcastindex.org/api/1.0"
USER_AGENT = "Earshot/1.0 (MSML 650 course project)"
SOURCE = "Podcast Index API (https://podcastindex.org)"
DEFAULT_OUT = REPO_ROOT / "contracts" / "samples" / "catalog.json"

SHOWS_PER_GENRE = 6
EPISODES_PER_SHOW = 20
MIN_EPISODES = 10  # skip shows with fewer playable episodes than this
CANDIDATES_PER_GENRE = 60  # trending shows considered per genre
EPISODES_TO_FETCH = 50  # newest episodes requested per show, before filtering
MAX_DURATION_SEC = 86_400  # position_sec <= 86400 (CONTEXT §6)
DESCRIPTION_CHARS = 600
FEATURED_COUNT = 20  # the FEATURED item's hand-picked episodes (§8.1)

SHOW_FIELDS = frozenset(
    {"show_id", "title", "author", "description", "image_url", "genre", "episode_count"}
)
EPISODE_FIELDS = frozenset(
    {"show_id", "episode_id", "title", "audio_url", "duration_sec", "published_at", "image_url", "genre"}
)

#: ``get(path, params)`` -> decoded JSON response.
Get = Callable[[str, Mapping[str, Any]], dict[str, Any]]


def auth_headers(key: str, secret: str, epoch_s: int) -> dict[str, str]:
    """Podcast Index auth headers: ``Authorization`` = sha1(key + secret + X-Auth-Date), hex."""
    date = str(epoch_s)
    return {
        "User-Agent": USER_AGENT,
        "X-Auth-Key": key,
        "X-Auth-Date": date,
        "Authorization": hashlib.sha1((key + secret + date).encode()).hexdigest(),
    }


def api_client(key: str, secret: str) -> Get:
    """Return a ``get`` function that calls the Podcast Index API."""

    def get(path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers=auth_headers(key, secret, int(time.time())))
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    return get


def clean_text(value: Any, limit: int | None = None) -> str:
    """Plain text from feed HTML: entities decoded, tags removed, whitespace collapsed."""
    text = " ".join(re.sub(r"<[^>]*>", " ", html.unescape(str(value or ""))).split())
    if limit is not None and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def category_ids(get: Get) -> dict[str, int]:
    """Podcast Index category id for each genre, matched by display name (§8.3)."""

    def key(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    by_name = {key(c["name"]): int(c["id"]) for c in get("/categories/list", {})["feeds"]}
    missing = [genre for genre, label in names.GENRES.items() if key(label) not in by_name]
    if missing:
        raise SystemExit(f"No Podcast Index category matches genres {missing}")
    return {genre: by_name[key(label)] for genre, label in names.GENRES.items()}


def _playable(item: Mapping[str, Any]) -> bool:
    duration = item.get("duration")
    return (
        str(item.get("enclosureUrl") or "").startswith("https://")
        and str(item.get("enclosureType") or "").startswith("audio/")
        and type(duration) is int
        and 0 < duration <= MAX_DURATION_SEC
        and bool(clean_text(item.get("title")))
        and (item.get("datePublished") or 0) > 0
    )


def playable_episodes(items: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The newest ``EPISODES_PER_SHOW`` playable items, newest first."""
    playable = sorted(filter(_playable, items), key=lambda item: item["datePublished"], reverse=True)
    return playable[:EPISODES_PER_SHOW]


def to_show(feed: Mapping[str, Any], genre: str, episode_count: int) -> dict[str, Any]:
    return {
        "show_id": str(feed["id"]),
        "title": clean_text(feed.get("title")),
        "author": clean_text(feed.get("author") or feed.get("ownerName")),
        "description": clean_text(feed.get("description"), DESCRIPTION_CHARS),
        "image_url": feed.get("artwork") or feed.get("image") or "",
        "genre": genre,
        "episode_count": episode_count,
    }


def to_episode(item: Mapping[str, Any], show: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "show_id": show["show_id"],
        "episode_id": str(item["id"]),
        "title": clean_text(item.get("title")),
        "audio_url": item["enclosureUrl"],
        "duration_sec": item["duration"],
        "published_at": item["datePublished"],
        "image_url": item.get("image") or item.get("feedImage") or show["image_url"],
        "genre": show["genre"],
    }


def build_catalog(get: Get) -> dict[str, Any]:
    """Pick the shows and episodes (see the module docstring) and return the catalog."""
    shows: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    taken: set[str] = set()
    for genre, category in category_ids(get).items():
        params = {"max": CANDIDATES_PER_GENRE, "lang": "en", "cat": category}
        picked = 0
        for feed in get("/podcasts/trending", params)["feeds"]:
            if picked == SHOWS_PER_GENRE:
                break
            has_art = feed.get("artwork") or feed.get("image")
            if str(feed["id"]) in taken or not has_art or not clean_text(feed.get("title")):
                continue
            items = get("/episodes/byfeedid", {"id": feed["id"], "max": EPISODES_TO_FETCH})["items"]
            playable = playable_episodes(items)
            if len(playable) < MIN_EPISODES:
                continue
            show = to_show(feed, genre, len(playable))
            taken.add(show["show_id"])
            shows.append(show)
            episodes.extend(to_episode(item, show) for item in playable)
            picked += 1
        if picked < SHOWS_PER_GENRE:
            print(f"warning: only {picked} usable shows for genre {genre}", file=sys.stderr)
    return {"source": SOURCE, "generated_at": now_ms(), "shows": shows, "episodes": episodes}


def check_catalog(catalog: Mapping[str, Any]) -> list[str]:
    """Problems that would break seeding or other members' code; empty if the catalog is good."""
    problems: list[str] = []
    show_list, episode_list = catalog.get("shows", []), catalog.get("episodes", [])
    shows = {show.get("show_id"): show for show in show_list}
    if len(shows) != len(show_list):
        problems.append("duplicate show_id")
    # Progress and trending keys use episode_id alone (§8.1), so it must be unique overall.
    episode_ids = [episode.get("episode_id") for episode in episode_list]
    if len(set(episode_ids)) != len(episode_ids):
        problems.append("duplicate episode_id")
    problems += [f"no shows for genre {g}" for g in names.GENRES if g not in {s.get("genre") for s in show_list}]

    counts = Counter(episode.get("show_id") for episode in episode_list)
    for show_id, show in shows.items():
        if set(show) != SHOW_FIELDS:
            problems.append(f"show {show_id}: fields {sorted(set(show) ^ SHOW_FIELDS)} differ from §8.1")
        if show.get("genre") not in names.GENRES:
            problems.append(f"show {show_id}: unknown genre {show.get('genre')!r}")
        if not show.get("title") or not show.get("image_url"):
            problems.append(f"show {show_id}: missing title or image_url")
        if show.get("episode_count") != counts[show_id]:
            problems.append(f"show {show_id}: episode_count {show.get('episode_count')} != {counts[show_id]}")

    for episode in episode_list:
        where = f"episode {episode.get('episode_id')}"
        show = shows.get(episode.get("show_id"))
        duration = episode.get("duration_sec")
        if set(episode) != EPISODE_FIELDS:
            problems.append(f"{where}: fields {sorted(set(episode) ^ EPISODE_FIELDS)} differ from §8.1")
        if show is None:
            problems.append(f"{where}: unknown show {episode.get('show_id')!r}")
        elif episode.get("genre") != show.get("genre"):
            problems.append(f"{where}: genre differs from its show")
        if not str(episode.get("audio_url") or "").startswith("https://"):
            problems.append(f"{where}: audio_url isn't https")
        if type(duration) is not int or not 0 < duration <= MAX_DURATION_SEC:
            problems.append(f"{where}: duration_sec {duration!r} isn't 1..{MAX_DURATION_SEC}")
        if not episode.get("title") or type(episode.get("published_at")) is not int:
            problems.append(f"{where}: missing title or published_at")

    # Added by hand (M2-02, check_featured.py), so it's checked only when present.
    featured = catalog.get("featured")
    if featured is not None:
        by_id = {episode.get("episode_id"): episode for episode in episode_list}
        if len(featured) != FEATURED_COUNT or len({f.get("episode_id") for f in featured}) != len(featured):
            problems.append(f"featured must list {FEATURED_COUNT} different episodes")
        for item in featured:
            episode = by_id.get(item.get("episode_id"))
            if set(item) != {"show_id", "episode_id"} or episode is None or episode["show_id"] != item["show_id"]:
                problems.append(f"featured {item}: not an episode in this catalog")
    return problems


def read_credentials(stage: str) -> tuple[str, str]:
    """Podcast Index key and secret from SSM SecureString parameters (CONTEXT §9)."""
    import boto3

    wanted = [names.ssm_podcastindex_key(stage), names.ssm_podcastindex_secret(stage)]
    found = boto3.client("ssm", region_name=names.REGION).get_parameters(Names=wanted, WithDecryption=True)
    if found["InvalidParameters"]:
        raise SystemExit(
            f"Missing SSM parameters {found['InvalidParameters']}. Create them first "
            "(see the docstring of scripts/catalog/fetch_catalog.py)."
        )
    values = {param["Name"]: param["Value"] for param in found["Parameters"]}
    return values[wanted[0]], values[wanted[1]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build contracts/samples/catalog.json from Podcast Index.")
    parser.add_argument("--stage", required=True, help="your stage; its SSM parameters hold the API keys")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"default: {DEFAULT_OUT}")
    args = parser.parse_args(argv)
    names.validate_stage(args.stage)

    catalog = build_catalog(api_client(*read_credentials(args.stage)))
    problems = check_catalog(catalog)
    if problems:
        print("Catalog NOT written:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    per_genre = dict(Counter(show["genre"] for show in catalog["shows"]))
    print(f"Wrote {args.out}: {len(catalog['shows'])} shows, {len(catalog['episodes'])} episodes {per_genre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

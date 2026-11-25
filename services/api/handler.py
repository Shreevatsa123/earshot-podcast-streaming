"""API Lambda: all read routes (CONTEXT §7.3, §7.4).

Owner: M2 · Tracker: M2-05 (routes), M2-06 (``/home``) · Function: ``earshot-<stage>-api``
Handler: ``api.handler.main`` · Env (CONTEXT §9): STAGE, TABLE_NAME, FLAGS_PARAM, ALLOWED_GENRES.

One Lambda behind the HTTP API (payload 2.0); ``event["routeKey"]`` picks the route.
Every route except ``/health`` sits behind the JWT authorizer, so the token's claims are
already verified. Errors use the §7.1 shape; anything unexpected is logged and becomes a 500.
"""

from __future__ import annotations

import functools
import json
import os
import time
from collections.abc import Callable, Iterable
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

from shared import names
from shared.clock import now_ms, utc_date
from shared.http import error_response, is_simulator, json_response, jwt_claims
from shared.log import emit_metrics, log

SHOW_FIELDS = ("show_id", "title", "author", "image_url", "genre", "episode_count")
SIM_USER_HEADER = "x-earshot-sim-user"  # HTTP API lowercases header names
BATCH_GET_MAX = 100
ROW_LIMIT = 10  # items per /home row
TRENDING_MIN = 5  # below this, the trending row is filled up from POPULAR (§7.4 rule 2)
FLAGS_TTL_MS = 10_000  # flags are cached for 10 s (§9)
RECS_TIMEOUT_SEC = 0.3  # the recs lookup's connect/read timeout (§7.4 rule 4)

Response = dict[str, Any]


class ApiError(Exception):
    """A client error with a §7.1 code, e.g. ``ApiError("NOT_FOUND", "Unknown show 42")``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---- AWS clients (created once per container) --------------------------------------------


@functools.cache
def _dynamodb() -> Any:
    return boto3.resource("dynamodb")


def _table() -> Any:
    return _dynamodb().Table(names.required_env("TABLE_NAME"))


@functools.cache
def _fast_dynamodb() -> Any:
    """Only for the recs lookup (§7.4 rule 4): 0.3 s timeouts and 1 retry, so a slow
    DynamoDB call turns into the popular fallback instead of a slow or failed /home."""
    config = Config(
        connect_timeout=RECS_TIMEOUT_SEC,
        read_timeout=RECS_TIMEOUT_SEC,
        retries={"total_max_attempts": 2, "mode": "standard"},
    )
    return boto3.resource("dynamodb", config=config)


@functools.cache
def _ssm() -> Any:
    return boto3.client("ssm")


_flags_cache: tuple[int, dict[str, bool]] = (0, {})


def get_flags() -> dict[str, bool]:
    """The feature flags from SSM, cached for 10 s. If SSM can't be read, the last known
    flags (or the defaults) are used: flags must never break /home."""
    global _flags_cache
    expires_at, flags = _flags_cache
    if now_ms() < expires_at:
        return flags
    try:
        raw = _ssm().get_parameter(Name=names.required_env("FLAGS_PARAM"))["Parameter"]["Value"]
        flags = {**names.DEFAULT_FLAGS, **json.loads(raw)}
    except Exception as err:
        log("flags unreadable, keeping the last known ones", level="WARNING", error=f"{type(err).__name__}: {err}")
        flags = flags or dict(names.DEFAULT_FLAGS)
    _flags_cache = (now_ms() + FLAGS_TTL_MS, flags)
    return flags


def query_all(**kwargs: Any) -> list[dict[str, Any]]:
    """Every item of a table query, following pagination."""
    items: list[dict[str, Any]] = []
    while True:
        page = _table().query(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def batch_get(keys: Iterable[tuple[str, str]]) -> list[dict[str, Any]]:
    """Items for ``(PK, SK)`` keys with BatchGetItem (100 per call, unprocessed keys retried)."""
    table_name = names.required_env("TABLE_NAME")
    pending = [{"PK": pk, "SK": sk} for pk, sk in dict.fromkeys(keys)]
    items: list[dict[str, Any]] = []
    for start in range(0, len(pending), BATCH_GET_MAX):
        request: dict[str, Any] = {table_name: {"Keys": pending[start : start + BATCH_GET_MAX]}}
        while request:
            page = _dynamodb().batch_get_item(RequestItems=request)
            items += page["Responses"].get(table_name, [])
            request = page.get("UnprocessedKeys") or {}
            if request:
                time.sleep(0.05)
    return items


# ---- shared helpers ------------------------------------------------------------------------


def episode_card(episode: dict[str, Any], show_title: str) -> dict[str, Any]:
    """An EpisodeCard (§7.1) without ``position_sec``."""
    return {
        "show_id": episode["show_id"],
        "episode_id": episode["episode_id"],
        "title": episode["title"],
        "show_title": show_title,
        "image_url": episode["image_url"],
        "audio_url": episode["audio_url"],
        "duration_sec": episode["duration_sec"],
        "genre": episode["genre"],
    }


def hydrate(refs: Iterable[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """``episode_id -> EpisodeCard`` for ``(show_id, episode_id)`` pairs, read with one
    BatchGetItem pass over the episode items and their shows' META (§7.4 rule 6).
    Episodes that aren't in the catalog are left out."""
    refs = list(refs)
    keys = [(f"SHOW#{s}", f"EP#{e}") for s, e in refs] + [(f"SHOW#{s}", "META") for s, _ in refs]
    items = batch_get(keys)
    titles = {item["show_id"]: item["title"] for item in items if item["SK"] == "META"}
    return {
        item["episode_id"]: episode_card(item, titles.get(item["show_id"], ""))
        for item in items
        if item["SK"].startswith("EP#")
    }


def int_param(event: dict[str, Any], name: str, default: int, low: int, high: int) -> int:
    raw = (event.get("queryStringParameters") or {}).get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = low - 1
    if not low <= value <= high:
        raise ApiError("BAD_REQUEST", f"{name} must be a whole number from {low} to {high}")
    return value


def caller_user_id(event: dict[str, Any]) -> str:
    """The user the request acts as (§7.1, §7.2): the token's ``sub``, or for the
    ``simulator`` group the ``sim-*`` user named in ``X-Earshot-Sim-User``."""
    claims = jwt_claims(event)
    if not claims.get("sub"):
        raise ApiError("UNAUTHORIZED", "Missing token")
    sim_user = (event.get("headers") or {}).get(SIM_USER_HEADER)
    if sim_user and is_simulator(claims):
        if not sim_user.startswith("sim-"):
            raise ApiError("FORBIDDEN", f"{SIM_USER_HEADER} must name a sim-* user")
        return sim_user
    return claims["sub"]


# ---- routes (§7.3) -------------------------------------------------------------------------


def health(event: dict[str, Any]) -> Response:
    return json_response(200, {"status": "ok", "stage": os.environ.get("STAGE", "unknown")})


def genres(event: dict[str, Any]) -> Response:
    return json_response(200, {"genres": [{"id": gid, "name": name} for gid, name in names.GENRES.items()]})


def shows(event: dict[str, Any]) -> Response:
    genre = (event.get("queryStringParameters") or {}).get("genre")
    if genre not in names.GENRES:
        raise ApiError("BAD_REQUEST", f"genre must be one of {', '.join(names.GENRES)}")
    limit = int_param(event, "limit", 20, 1, 50)
    page = _table().query(IndexName="GSI1", KeyConditionExpression=Key("GSI1PK").eq(f"GENRE#{genre}"), Limit=limit)
    return json_response(200, {"shows": [{f: item[f] for f in SHOW_FIELDS} for item in page["Items"]]})


def show_detail(event: dict[str, Any]) -> Response:
    show_id = event["pathParameters"]["showId"]
    items = query_all(KeyConditionExpression=Key("PK").eq(f"SHOW#{show_id}"))
    meta = next((item for item in items if item["SK"] == "META"), None)
    if meta is None:
        raise ApiError("NOT_FOUND", f"Unknown show {show_id}")
    episodes = sorted(
        (item for item in items if item["SK"].startswith("EP#")), key=lambda e: e["published_at"], reverse=True
    )
    return json_response(
        200,
        {
            "show": {f: meta[f] for f in (*SHOW_FIELDS, "description")},
            "episodes": [episode_card(e, meta["title"]) for e in episodes],
        },
    )


def progress(event: dict[str, Any]) -> Response:
    episode_id = event["pathParameters"]["episodeId"]
    key = {"PK": f"USER#{caller_user_id(event)}", "SK": f"PROG#{episode_id}"}
    # Strongly consistent: the position must show up right after a pause (S2).
    item = _table().get_item(Key=key, ConsistentRead=True).get("Item")
    if item is None:
        return json_response(200, {"episode_id": episode_id, "position_sec": 0, "completed": False, "updated_at": None})
    return json_response(
        200,
        {
            "episode_id": episode_id,
            "position_sec": item["position_sec"],
            "completed": item["completed"],
            "updated_at": item["updated_at"],
        },
    )


def trending_items(limit: int) -> tuple[str, list[dict[str, Any]]]:
    """Today's (UTC) top episodes by plays, as EpisodeCards with ``plays`` (also used by /home)."""
    today = utc_date(now_ms())
    counters = query_all(KeyConditionExpression=Key("PK").eq(f"TREND#{today}"))
    ranked = sorted(counters, key=lambda c: (-c["plays"], c["SK"]))
    items: list[dict[str, Any]] = []
    # Hydrate in rank order until there are `limit` cards: an episode missing from the
    # catalog is skipped and the next one moves up. 50 refs = at most 100 BatchGet keys.
    for start in range(0, len(ranked), 50):
        chunk = ranked[start : start + 50]
        cards = hydrate((c["show_id"], c["SK"].removeprefix("EP#")) for c in chunk)
        items += [
            {**cards[episode_id], "plays": c["plays"]}
            for c in chunk
            if (episode_id := c["SK"].removeprefix("EP#")) in cards
        ]
        if len(items) >= limit:
            break
    return today, items[:limit]


def trending(event: dict[str, Any]) -> Response:
    today, items = trending_items(int_param(event, "limit", 10, 1, 20))
    return json_response(200, {"date": today, "items": items})


# ---- GET /home (§7.4) ----------------------------------------------------------------------


def home_row(row_id: str, title: str, source: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A /home row, or None when it has no items (empty rows are omitted)."""
    return {"id": row_id, "title": title, "source": source, "items": items[:ROW_LIMIT]} if items else None


def global_list(pk: str) -> list[dict[str, Any]]:
    """``items`` of the POPULAR or FEATURED item (``<pk>`` / ``GLOBAL``), or [] if it's missing."""
    item = _table().get_item(Key={"PK": pk, "SK": "GLOBAL"}).get("Item")
    return item["items"] if item else []


def continue_row(user_id: str) -> dict[str, Any] | None:
    """Rule 1: up to 10 unfinished episodes, most recently updated first, with position_sec."""
    progress_items = query_all(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("PROG#")
    )
    latest = sorted((p for p in progress_items if not p["completed"]), key=lambda p: p["updated_at"], reverse=True)
    latest = latest[:ROW_LIMIT]
    cards = hydrate((p["show_id"], p["episode_id"]) for p in latest)
    items = [{**cards[p["episode_id"]], "position_sec": p["position_sec"]} for p in latest if p["episode_id"] in cards]
    return home_row("continue", "Continue Listening", "progress", items)


def trending_row(popular: Callable[[], list[dict[str, Any]]]) -> dict[str, Any] | None:
    """Rule 2: today's top 10; with fewer than 5, filled up from POPULAR (no repeats)."""
    _, items = trending_items(ROW_LIMIT)
    if len(items) < TRENDING_MIN:
        seen = {item["episode_id"] for item in items}
        extra = [p for p in popular() if p["episode_id"] not in seen]
        cards = hydrate((p["show_id"], p["episode_id"]) for p in extra)
        items += [{**cards[p["episode_id"]], "plays": p["plays"]} for p in extra if p["episode_id"] in cards]
    return home_row("trending", "Trending Now", "trending", items)


def personalized_rows(user_id: str) -> list[dict[str, Any]]:
    """Rule 3: up to 2 "Because you listened to …" rows from the user's RECS item, which is
    read with the short-timeout client. [] when the user has no RECS item yet."""
    recs_table = _fast_dynamodb().Table(names.required_env("TABLE_NAME"))
    recs = recs_table.get_item(Key={"PK": f"USER#{user_id}", "SK": "RECS"}).get("Item")
    if not recs:
        return []
    rows = []
    for number, rec in enumerate(recs["rows"][:2], start=1):
        refs = [(rec["seed_show_id"], rec["seed_episode_id"])] + [(i["show_id"], i["episode_id"]) for i in rec["items"]]
        cards = hydrate(refs)
        seed = cards.get(rec["seed_episode_id"])
        title = f"Because you listened to {seed['title']}" if seed else "Recommended for you"
        items = [cards[i["episode_id"]] for i in rec["items"] if i["episode_id"] in cards]
        if row := home_row(f"recs-{number}", title, "personalized", items):
            rows.append(row)
    return rows


def fallback_row(popular: Callable[[], list[dict[str, Any]]]) -> dict[str, Any] | None:
    """Rule 3's fallback: "Popular on Earshot" from POPULAR, or from FEATURED if it's missing."""
    refs = popular() or global_list("FEATURED")
    cards = hydrate((r["show_id"], r["episode_id"]) for r in refs)
    items = [cards[r["episode_id"]] for r in refs if r["episode_id"] in cards]
    return home_row("popular", "Popular on Earshot", "popular_fallback", items)


def home(event: dict[str, Any]) -> Response:
    user_id = caller_user_id(event)
    flags = get_flags()
    popular = functools.cache(lambda: global_list("POPULAR"))  # read at most once per request
    rows = [continue_row(user_id), trending_row(popular)]

    # Rule 4: a recs failure, a timeout or fault injection → the fallback, marked degraded.
    degraded = bool(flags.get("recs_fault_injection"))
    personalized: list[dict[str, Any]] = []
    if not degraded and flags.get("recs_enabled"):
        try:
            personalized = personalized_rows(user_id)
        except Exception as err:  # timeouts included: /home must never 5xx because of recs
            log("recs lookup failed", level="WARNING", error=f"{type(err).__name__}: {err}")
            degraded = True
    if degraded:
        emit_metrics({"HomeFallback": 1})
    rows += personalized or [fallback_row(popular)]

    body = {"user_id": user_id, "generated_at": now_ms(), "degraded": degraded, "rows": [r for r in rows if r]}
    return json_response(200, body)


ROUTES: dict[str, Callable[[dict[str, Any]], Response]] = {
    "GET /health": health,
    "GET /genres": genres,
    "GET /shows": shows,
    "GET /shows/{showId}": show_detail,
    "GET /progress/{episodeId}": progress,
    "GET /trending": trending,
    "GET /home": home,
}


def main(event: dict[str, Any], context: Any) -> Response:
    started = time.perf_counter()
    route = event.get("routeKey", "")
    try:
        handler = ROUTES.get(route)
        if handler is None:
            raise ApiError("NOT_FOUND", f"No route {route!r}")
        response = handler(event)
    except ApiError as err:
        response = error_response(err.code, str(err))
    except Exception as err:  # never leak internals; the log has the details
        log("unhandled error", level="ERROR", route=route, error=f"{type(err).__name__}: {err}")
        response = error_response("INTERNAL", "Something went wrong")
    log("request", route=route, status=response["statusCode"], ms=round((time.perf_counter() - started) * 1000))
    return response

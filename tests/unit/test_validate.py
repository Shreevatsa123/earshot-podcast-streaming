"""M3-01: event validation rules (CONTEXT §6, §7.5)."""

import pytest

from shared import names
from shared.validate import DEFAULT_GENRES, EVENT_FIELDS, MIN_CLIENT_TS_MS, order_fields, validate_event

NOW = 1_794_000_000_000  # 2026-11-11


def event(**overrides):
    base = {
        "event_id": "8f0c1f9e-6c43-4b5e-9a37-0a6f8a1c2d11",
        "session_id": "b1d2c3d4-e5f6-4789-a012-3456789abcde",
        "show_id": "920666",
        "episode_id": "16795090",
        "genre": "true-crime",
        "event_type": "pause",
        "position_sec": 734,
        "duration_sec": 2810,
        "client_ts": NOW - 1000,
        "region": "us-east",
        "device": "web",
    }
    base.update(overrides)
    return base


def test_valid_event_is_cleaned():
    clean, reason = validate_event(event(extra="dropped", server_ts=1, user_id="spoof"), now_ms=NOW)
    assert reason is None
    assert clean["schema_version"] == 1
    assert "extra" not in clean
    assert "server_ts" not in clean and "user_id" not in clean  # ingest sets these
    assert set(clean) == set(EVENT_FIELDS) - {"user_id", "server_ts"}


def test_default_genres_match_names():
    assert tuple(names.GENRES) == DEFAULT_GENRES


@pytest.mark.parametrize("raw", [None, [], "x", 3])
def test_not_an_object(raw):
    assert validate_event(raw, now_ms=NOW) == (None, "INVALID_JSON")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", "not-a-uuid"),
        ("event_id", "8f0c1f9e-6c43-1b5e-9a37-0a6f8a1c2d11"),  # version 1, not 4
        ("event_id", None),
        ("schema_version", 2),
        ("session_id", ""),
        ("show_id", ""),
        ("show_id", 920666),
        ("episode_id", "x" * 65),
        ("genre", "jazz"),
        ("event_type", "stop"),
        ("position_sec", -1),
        ("position_sec", 86_401),
        ("position_sec", 12.5),
        ("position_sec", True),
        ("position_sec", "10"),
        ("duration_sec", 0),
        ("client_ts", MIN_CLIENT_TS_MS - 1),
        ("client_ts", NOW + 300_001),
        ("region", "mars"),
        ("device", "tv"),
    ],
)
def test_bad_field(field, value):
    assert validate_event(event(**{field: value}), now_ms=NOW) == (None, f"INVALID_FIELD:{field}")


def test_missing_field():
    raw = event()
    del raw["region"]
    assert validate_event(raw, now_ms=NOW) == (None, "INVALID_FIELD:region")


def test_edges_are_allowed():
    for overrides in (
        {"position_sec": 0},
        {"position_sec": 86_400},
        {"client_ts": MIN_CLIENT_TS_MS},
        {"client_ts": NOW + 300_000},
        {"position_sec": 12.0},  # integral float from a browser
        {"schema_version": 1},
        {"event_id": "8F0C1F9E-6C43-4B5E-9A37-0A6F8A1C2D11"},
    ):
        clean, reason = validate_event(event(**overrides), now_ms=NOW)
        assert reason is None, overrides
    assert validate_event(event(position_sec=12.0), now_ms=NOW)[0]["position_sec"] == 12


def test_allowed_genres_override():
    assert validate_event(event(genre="news"), now_ms=NOW, allowed_genres=("comedy",))[1] == "INVALID_FIELD:genre"


def test_order_fields():
    full = {field: i for i, field in enumerate(reversed(EVENT_FIELDS))}
    assert list(order_fields(full)) == list(EVENT_FIELDS)

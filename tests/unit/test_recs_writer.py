"""M5-04: the recs writer (CONTEXT §8.1, §10): parsing Athena's CSVs into RECS and POPULAR items."""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest

from recs_writer.handler import (
    POPULAR_COLUMNS,
    RECS_COLUMNS,
    ResultError,
    parse_popular,
    parse_recs,
    popular_item,
    recs_item,
)


def athena_csv(columns: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    """A result file the way Athena writes it: a header, then every value in double quotes."""
    out = io.StringIO()
    writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return out.getvalue()


def rec(user: str, seed_rank: int, seed_ep: str, item_rank: int, ep: str, score: int = 1, source: str = "co"):
    """One recs.sql output row; each episode is its own show (show-<episode>)."""
    return (user, seed_rank, f"show-{seed_ep}", seed_ep, item_rank, f"show-{ep}", ep, score, source)


def recs_csv(*rows: tuple[Any, ...]) -> str:
    return athena_csv(RECS_COLUMNS, list(rows))


# ---- parse_recs ---------------------------------------------------------------------------


def test_recs_become_one_item_per_user_in_rank_order():
    text = recs_csv(
        rec("u1", 2, "s2", 1, "x9", 4),
        rec("u1", 1, "s1", 2, "x2", 3),  # file order doesn't matter
        rec("u1", 1, "s1", 1, "x1", 5),
        rec("u2", 1, "t1", 1, "y1", 0, "genre"),
    )
    assert parse_recs(text) == {
        "u1": [
            {
                "seed_show_id": "show-s1",
                "seed_episode_id": "s1",
                "items": [
                    {"show_id": "show-x1", "episode_id": "x1", "score": 5},
                    {"show_id": "show-x2", "episode_id": "x2", "score": 3},
                ],
            },
            {
                "seed_show_id": "show-s2",
                "seed_episode_id": "s2",
                "items": [{"show_id": "show-x9", "episode_id": "x9", "score": 4}],
            },
        ],
        "u2": [{"seed_show_id": "show-t1", "seed_episode_id": "t1", "items": [{"show_id": "show-y1", "episode_id": "y1", "score": 0}]}],
    }


def test_item_ranks_sort_as_numbers_not_text():
    """Athena quotes numbers, so "10" sorts before "2" unless they're converted."""
    text = recs_csv(*(rec("u1", 1, "s1", rank, f"x{rank:02d}") for rank in (10, 2, 1, 9, 3, 4, 5, 6, 7, 8)))
    items = parse_recs(text)["u1"][0]["items"]
    assert [item["episode_id"] for item in items] == [f"x{n:02d}" for n in range(1, 11)]
    assert all(isinstance(item["score"], int) for item in items)


def test_a_user_can_have_only_a_second_seed_row():
    """Seed 1 can run out of recommendations while seed 2 still has some."""
    assert [r["seed_episode_id"] for r in parse_recs(recs_csv(rec("u1", 2, "s2", 1, "x1")))["u1"]] == ["s2"]


def test_header_only_means_no_users():
    assert parse_recs(recs_csv()) == {}


@pytest.mark.parametrize(
    "text",
    [
        recs_csv(rec("u1", 3, "s3", 1, "x1")),  # a third row
        recs_csv(rec("u1", 1, "s1", 11, "x1")),  # an 11th item
        recs_csv(rec("u1", 1, "s1", 0, "x1")),
        recs_csv(rec("u1", 1, "s1", 1, "x1", -1)),  # negative score
        recs_csv(rec("u1", 1, "s1", 1, "x1"), rec("u1", 1, "other", 2, "x2")),  # seed changes
        recs_csv(rec("u1", 1, "s1", 1, "x1"), rec("u1", 1, "s1", 1, "x2")),  # rank repeated
        recs_csv(rec("u1", 1, "s1", 1, "x1"), rec("u1", 1, "s1", 3, "x3")),  # rank 2 missing
        recs_csv(("u1", "one", "show-s1", "s1", 1, "show-x1", "x1", 1, "co")),  # not a number
        recs_csv(("", 1, "show-s1", "s1", 1, "show-x1", "x1", 1, "co")),  # empty user
        athena_csv(("user_id", "seed_rank"), [("u1", 1)]),  # wrong columns
        "",  # no header at all
    ],
    ids=[
        "seed-rank-3",
        "item-rank-11",
        "item-rank-0",
        "negative-score",
        "seed-changes",
        "rank-repeated",
        "rank-gap",
        "not-a-number",
        "empty-user",
        "wrong-columns",
        "no-header",
    ],
)
def test_malformed_recs_fail_the_whole_run(text):
    with pytest.raises(ResultError):
        parse_recs(text)


# ---- parse_popular ------------------------------------------------------------------------


def popular_csv(*rows: tuple[Any, ...]) -> str:
    return athena_csv(POPULAR_COLUMNS, list(rows))


def test_popular_keeps_the_query_order_with_integer_plays():
    text = popular_csv(("show-b", "b", 12), ("show-a", "a", 7), ("show-c", "c", 7))
    assert parse_popular(text) == [
        {"show_id": "show-b", "episode_id": "b", "plays": 12},
        {"show_id": "show-a", "episode_id": "a", "plays": 7},
        {"show_id": "show-c", "episode_id": "c", "plays": 7},
    ]


def test_empty_popular():
    assert parse_popular(popular_csv()) == []


@pytest.mark.parametrize(
    "text",
    [
        popular_csv(*((f"show-{n}", f"e{n}", 1) for n in range(21))),  # 21 episodes
        popular_csv(("show-a", "a", 2), ("show-a", "a", 1)),  # repeated episode
        popular_csv(("show-a", "a", 0)),
        popular_csv(("show-a", "a", "many")),
        athena_csv(("episode_id", "plays"), [("a", 1)]),
    ],
    ids=["21-episodes", "repeated", "zero-plays", "not-a-number", "wrong-columns"],
)
def test_malformed_popular_fails_the_whole_run(text):
    with pytest.raises(ResultError):
        parse_popular(text)


# ---- Items --------------------------------------------------------------------------------


def test_recs_item_shape_matches_what_home_reads():
    """§8.1, and the fields M2's /home uses: rows[:2], seed_show_id, seed_episode_id, items[].show_id/episode_id."""
    rows = parse_recs(recs_csv(rec("sim-000042", 1, "s1", 1, "x1", 2)))["sim-000042"]
    item = recs_item("sim-000042", rows, run_id="run-1", generated_at=1_794_614_400_000)
    assert item == {
        "PK": "USER#sim-000042",
        "SK": "RECS",
        "rows": rows,
        "generated_at": 1_794_614_400_000,
        "run_id": "run-1",
    }
    assert set(item["rows"][0]) == {"seed_show_id", "seed_episode_id", "items"}
    assert set(item["rows"][0]["items"][0]) == {"show_id", "episode_id", "score"}


def test_popular_item_shape():
    items = parse_popular(popular_csv(("show-a", "a", 3)))
    assert popular_item(items, run_id="run-1", generated_at=5) == {
        "PK": "POPULAR",
        "SK": "GLOBAL",
        "items": [{"show_id": "show-a", "episode_id": "a", "plays": 3}],
        "generated_at": 5,
        "run_id": "run-1",
    }

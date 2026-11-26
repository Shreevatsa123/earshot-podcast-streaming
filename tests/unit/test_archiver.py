"""M5-02: the archiver (CONTEXT §9, §10): batch planning, then the S3 write with moto."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError

from archiver import handler
from archiver.handler import (
    decode_message,
    encode_lines,
    hour_folder,
    lake_line,
    object_key,
    plan_batch,
)
from shared.validate import EVENT_FIELDS

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_EVENTS = [
    json.loads(line)
    for line in (ROOT / "contracts" / "samples" / "events.jsonl").read_text(encoding="utf-8").splitlines()
]
NOV_14 = 1_794_614_400_000  # 2026-11-14T00:00:00Z
HOUR = 3_600_000


def record(events: Any, message_id: str = "msg-1") -> dict[str, Any]:
    """An SQS record as Lambda delivers it with raw message delivery: body = {"events": [...]}."""
    return {"messageId": message_id, "body": json.dumps({"events": events})}


def sample(server_ts: int | None = None, **fields: Any) -> dict[str, Any]:
    """A copy of the first sample event, with any field overridden."""
    event = dict(SAMPLE_EVENTS[0])
    if server_ts is not None:
        event["server_ts"] = server_ts
    event.update(fields)
    return event


# ---- hour_folder / lake_line ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("server_ts", "folder"),
    [
        (NOV_14, "dt=2026-11-14/hour=00"),
        (NOV_14 + 9 * HOUR + 1, "dt=2026-11-14/hour=09"),  # 2 digits, like the projection
        (NOV_14 + 24 * HOUR - 1, "dt=2026-11-14/hour=23"),  # 23:59:59.999 stays on its day
        (NOV_14 + 24 * HOUR, "dt=2026-11-15/hour=00"),
    ],
)
def test_hour_folder_is_the_utc_hour_of_server_ts(server_ts, folder):
    assert hour_folder(server_ts) == folder


def test_lake_line_has_exactly_the_contract_fields_in_order():
    folder, line = lake_line(sample(NOV_14, extra="dropped"))
    assert folder == "dt=2026-11-14/hour=00"
    assert list(json.loads(line)) == list(EVENT_FIELDS)
    assert "\n" not in line


@pytest.mark.parametrize(
    "event",
    [
        "not an object",
        {k: v for k, v in SAMPLE_EVENTS[0].items() if k != "genre"},  # a missing field
        {**SAMPLE_EVENTS[0], "server_ts": "1794614400000"},  # a string
        {**SAMPLE_EVENTS[0], "server_ts": True},  # bool is an int in Python
        {**SAMPLE_EVENTS[0], "server_ts": 0},
    ],
    ids=["not-object", "missing-field", "string-ts", "bool-ts", "zero-ts"],
)
def test_lake_line_rejects_events_it_cannot_place(event):
    assert lake_line(event) is None


# ---- decode_message -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [None, "not json", json.dumps([1, 2]), json.dumps({"events": "nope"}), json.dumps({"other": []})],
    ids=["no-body", "not-json", "list", "events-not-list", "no-events"],
)
def test_decode_message_rejects_bodies_that_are_not_an_events_object(body):
    with pytest.raises(ValueError):
        decode_message({"messageId": "m", "body": body})


def test_decode_message_returns_the_events():
    assert decode_message(record([sample(), sample()])) == [sample(), sample()]


# ---- plan_batch ---------------------------------------------------------------------------


def test_plan_groups_events_by_hour_across_messages():
    plan = plan_batch(
        [
            record([sample(NOV_14 + 10), sample(NOV_14 + HOUR + 10)], "m1"),
            record([sample(NOV_14 + 20)], "m2"),
        ]
    )
    assert {folder: len(lines) for folder, lines in plan.lines_by_folder.items()} == {
        "dt=2026-11-14/hour=00": 2,
        "dt=2026-11-14/hour=01": 1,
    }
    assert plan.message_ids == ["m1", "m2"]
    assert plan.events == 3
    assert plan.malformed_message_ids == [] and plan.skipped_events == 0


def test_plan_reports_a_malformed_message_alone_and_keeps_the_rest():
    plan = plan_batch([record([sample(NOV_14)], "good"), {"messageId": "bad", "body": "{not json"}])
    assert plan.malformed_message_ids == ["bad"]
    assert plan.message_ids == ["good", "bad"]
    assert plan.events == 1


def test_plan_skips_unplaceable_events_but_keeps_their_message():
    broken = {k: v for k, v in sample(NOV_14).items() if k != "region"}
    plan = plan_batch([record([sample(NOV_14), broken, "junk"], "m1")])
    assert plan.events == 1
    assert plan.skipped_events == 2
    assert plan.malformed_message_ids == []


def test_plan_counts_records_without_a_message_id():
    plan = plan_batch([{"body": json.dumps({"events": [sample()]})}, "junk", record([sample()], "m1")])
    assert plan.unidentified_records == 2
    assert plan.message_ids == ["m1"]
    assert plan.events == 1


def test_plan_keeps_duplicates_for_the_queries_to_count_once():
    """SQS delivers at least once; the lake keeps both copies and the SQL counts DISTINCT event_id."""
    plan = plan_batch([record([sample(NOV_14)], "m1"), record([sample(NOV_14)], "m2")])
    assert plan.events == 2


def test_empty_batch():
    plan = plan_batch([])
    assert plan.lines_by_folder == {} and plan.message_ids == [] and plan.events == 0


# ---- object_key / encode_lines ------------------------------------------------------------


def test_object_key_matches_the_lake_layout():
    assert object_key("dt=2026-11-14/hour=00", "abc") == "events/dt=2026-11-14/hour=00/abc.json.gz"


def test_encode_lines_is_gzipped_json_lines():
    data = encode_lines(['{"a":1}', '{"a":2}'])
    assert gzip.decompress(data).decode("utf-8") == '{"a":1}\n{"a":2}\n'


# ---- The archiver's output is what the queries read ---------------------------------------


def test_count_events_sql_reads_the_archivers_files(tmp_path):
    """M3's 1,000 sample events (50 duplicates) -> archiver files -> athena/count_events.sql."""
    duckdb = pytest.importorskip("duckdb", reason="duckdb isn't installed")
    pytest.importorskip("aws_cdk", reason="aws-cdk-lib isn't installed; run `make install`")
    from earshot_infra.constructs.lake import EVENT_COLUMNS

    # 25 events per message, like ingest's largest requests.
    batch = [record(SAMPLE_EVENTS[i : i + 25], f"m{i}") for i in range(0, len(SAMPLE_EVENTS), 25)]
    plan = plan_batch(batch)
    for n, (folder, lines) in enumerate(plan.lines_by_folder.items()):
        path = tmp_path / object_key(folder, f"file-{n}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encode_lines(lines))

    types = {"string": "VARCHAR", "int": "INTEGER", "bigint": "BIGINT"}
    columns = ", ".join(f"'{name}': '{types[kind]}'" for name, kind in EVENT_COLUMNS)
    con = duckdb.connect()
    con.execute(
        f"CREATE VIEW events AS SELECT * FROM read_json('{(tmp_path / 'events').as_posix()}/*/*/*.json.gz', "
        f"format = 'newline_delimited', columns = {{{columns}}}, hive_partitioning = true, "
        "hive_types = {'dt': VARCHAR, 'hour': VARCHAR})"
    )
    sql = (ROOT / "athena" / "count_events.sql").read_text(encoding="utf-8")
    params = ["2026-11-14", "2026-11-15", NOV_14, NOV_14 + 24 * HOUR]
    assert con.execute(sql, params).fetchall() == [(1000, 950)]


# ---- main: the S3 write -------------------------------------------------------------------

BUCKET = "earshot-test-lake"
KEY_RE = re.compile(r"^events/dt=\d{4}-\d{2}-\d{2}/hour=\d{2}/[0-9a-f-]{36}\.json\.gz$")


@pytest.fixture
def lake(monkeypatch):
    """A moto S3 bucket named in LAKE_BUCKET, like the function's env (CONTEXT §9)."""
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    for key, value in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("LAKE_BUCKET", BUCKET)
    with moto.mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        yield s3


def lake_objects(s3: Any) -> dict[str, list[dict[str, Any]]]:
    """Every object in the bucket: key -> its decoded JSON lines."""
    listing = s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])
    return {
        item["Key"]: [
            json.loads(line)
            for line in gzip.decompress(s3.get_object(Bucket=BUCKET, Key=item["Key"])["Body"].read())
            .decode("utf-8")
            .splitlines()
        ]
        for item in listing
    }


def last_log(capsys) -> dict[str, Any]:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert len(lines) == 1, "the archiver logs once per batch"
    return json.loads(lines[0])


def test_main_writes_one_gzipped_file_per_hour(lake, capsys):
    result = handler.main(
        {"Records": [record([sample(NOV_14 + 10), sample(NOV_14 + HOUR + 10)], "m1"), record([sample(NOV_14 + 20)], "m2")]},
        None,
    )
    assert result == {"batchItemFailures": []}
    objects = lake_objects(lake)
    assert all(KEY_RE.match(key) for key in objects)
    assert sorted((key.split("/")[1] + "/" + key.split("/")[2], len(lines)) for key, lines in objects.items()) == [
        ("dt=2026-11-14/hour=00", 2),
        ("dt=2026-11-14/hour=01", 1),
    ]
    assert all(list(line) == list(EVENT_FIELDS) for lines in objects.values() for line in lines)
    summary = last_log(capsys)
    assert summary["level"] == "INFO"
    assert (summary["events"], summary["files_written"], summary["failed_messages"]) == (3, 2, 0)


def test_main_reports_only_the_malformed_message(lake):
    result = handler.main({"Records": [record([sample(NOV_14)], "good"), {"messageId": "bad", "body": "{"}]}, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert len(lake_objects(lake)) == 1


def test_main_fails_the_whole_batch_when_s3_fails(lake, monkeypatch, capsys):
    monkeypatch.setenv("LAKE_BUCKET", "no-such-bucket")
    records = [record([sample(NOV_14)], "m1"), record([sample(NOV_14)], "m2"), {"messageId": "bad", "body": "{"}]
    result = handler.main({"Records": records}, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": m} for m in ("m1", "m2", "bad")]}
    summary = last_log(capsys)
    assert (summary["level"], summary["write_error"]) == ("ERROR", "NoSuchBucket")


class FlakyS3:
    """A stand-in S3 client: the first put succeeds, then every put fails."""

    def __init__(self) -> None:
        self.keys: list[str] = []

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> dict[str, Any]:  # noqa: N803 (boto3 names)
        if self.keys:
            raise ClientError({"Error": {"Code": "SlowDown", "Message": "try later"}}, "PutObject")
        self.keys.append(Key)
        return {}


def test_main_fails_the_whole_batch_even_after_a_partial_write(monkeypatch):
    """§10: file 1 stays written; the retry writes it again, and the queries count DISTINCT."""
    flaky = FlakyS3()
    monkeypatch.setattr(handler.boto3, "client", lambda service: flaky)
    monkeypatch.setenv("LAKE_BUCKET", BUCKET)
    result = handler.main({"Records": [record([sample(NOV_14), sample(NOV_14 + HOUR)], "m1")]}, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
    assert len(flaky.keys) == 1


def test_main_with_nothing_to_write_makes_no_s3_call(monkeypatch):
    def no_s3(service: str) -> Any:
        raise AssertionError("no S3 client needed")

    monkeypatch.setattr(handler.boto3, "client", no_s3)
    monkeypatch.delenv("LAKE_BUCKET", raising=False)
    assert handler.main({"Records": []}, None) == {"batchItemFailures": []}
    assert handler.main({"Records": [{"messageId": "bad", "body": "{"}]}, None) == {
        "batchItemFailures": [{"itemIdentifier": "bad"}]
    }

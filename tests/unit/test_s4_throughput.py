"""S4 throughput check (tests/acceptance/s4_throughput.py) with faked AWS clients."""

import json

import pytest

from acceptance import s4_throughput as s4
from earshot_infra.config import StageConfig

START_MS = 1_795_000_000_000  # 2026-11-18 07:46 UTC
END_MS = START_MS + 600_000


class FakeSqs:
    def __init__(self, depths):
        self.depths = {name: list(values) for name, values in depths.items()}

    def get_queue_url(self, QueueName):
        return {"QueueUrl": QueueName}

    def get_queue_attributes(self, QueueUrl, AttributeNames):
        values = self.depths.get(QueueUrl, [0])
        depth = values.pop(0) if len(values) > 1 else values[0]
        return {
            "Attributes": {
                "ApproximateNumberOfMessages": str(depth),
                "ApproximateNumberOfMessagesNotVisible": "0",
            }
        }


class FakeAthena:
    def __init__(self, total, distinct):
        self.total, self.distinct = total, distinct
        self.started = None
        self.states = ["RUNNING", "SUCCEEDED"]

    def start_query_execution(self, **kwargs):
        self.started = kwargs
        return {"QueryExecutionId": "q1"}

    def get_query_execution(self, QueryExecutionId):
        return {"QueryExecution": {"Status": {"State": self.states.pop(0)}}}

    def get_query_results(self, QueryExecutionId):
        header = {"Data": [{"VarCharValue": "total_rows"}, {"VarCharValue": "distinct_events"}]}
        row = {"Data": [{"VarCharValue": str(self.total)}, {"VarCharValue": str(self.distinct)}]}
        return {"ResultSet": {"Rows": [header, row]}}


class FakeCloudWatch:
    def __init__(self, values):
        self.values = values

    def get_metric_data(self, **kwargs):
        return {"MetricDataResults": [{"Values": self.values}]}


class FakeCtx:
    def __init__(self, sqs, athena, cloudwatch):
        self.cfg = StageConfig(stage="test", account="123456789012")
        self.stage = "test"
        self._clients = {"sqs": sqs, "athena": athena, "cloudwatch": cloudwatch}

    def client(self, service):
        return self._clients[service]


def write_report(tmp_path, monkeypatch, **overrides):
    report = {
        "run_id": "r1",
        "start_ms": START_MS,
        "end_ms": END_MS,
        "sent": 300_000,
        "accepted": 300_000,
        "rejected_by_reason": {},
        "achieved_rate": 500.0,
    }
    report.update(overrides)
    path = tmp_path / "r1.run-report.json"
    path.write_text(json.dumps(report))
    monkeypatch.setenv(s4.REPORT_ENV, str(path))
    return path


def make_ctx(cfg_depths=None, stored=300_000, total=300_050, metric=(300_000,)):
    ctx = FakeCtx(FakeSqs({}), FakeAthena(total, stored), FakeCloudWatch(list(metric)))
    if cfg_depths:
        ctx._clients["sqs"] = FakeSqs({getattr(ctx.cfg, k): v for k, v in cfg_depths.items()})
    return ctx


def test_passes_when_every_accepted_event_is_stored(tmp_path, monkeypatch):
    write_report(tmp_path, monkeypatch)
    ctx = make_ctx(cfg_depths={"hot_queue": [40, 0], "cold_queue": [900, 0]})
    result = s4.run(ctx, sleep=lambda s: None)
    assert result.passed, result.measured
    assert result.details["lost"] == 0
    assert result.details["stored_rows"] == 300_050  # retried duplicates don't count
    assert result.details["events_accepted_metric"] == 300_000
    assert result.details["drain_wait_s"] > 0
    params = ctx.client("athena").started["ExecutionParameters"]
    assert params == ["'2026-11-18'", "'2026-11-19'", str(START_MS), str(END_MS + 1)]
    assert ctx.client("athena").started["WorkGroup"] == ctx.cfg.athena_workgroup
    assert "--" not in ctx.client("athena").started["QueryString"]


def test_fails_when_events_are_lost(tmp_path, monkeypatch):
    write_report(tmp_path, monkeypatch)
    result = s4.run(make_ctx(stored=299_990), sleep=lambda s: None)
    assert not result.passed
    assert result.details["lost"] == 10


def test_fails_when_the_load_was_too_small(tmp_path, monkeypatch):
    write_report(tmp_path, monkeypatch, achieved_rate=300.0, accepted=180_000, sent=180_000)
    result = s4.run(make_ctx(stored=180_000), sleep=lambda s: None)
    assert not result.passed
    assert result.details["load_target_met"] is False


def test_fails_when_a_dlq_has_messages(tmp_path, monkeypatch):
    write_report(tmp_path, monkeypatch)
    result = s4.run(make_ctx(cfg_depths={"processor_dlq": [2]}), sleep=lambda s: None)
    assert not result.passed
    assert result.details["dlq_messages"]["earshot-test-processor-dlq"] == 2


def test_fails_when_queues_never_drain(tmp_path, monkeypatch):
    write_report(tmp_path, monkeypatch)
    result = s4.run(make_ctx(cfg_depths={"hot_queue": [5]}), sleep=lambda s: None)
    assert not result.passed
    assert result.details["queues_drained"] is False


def test_newest_report_in_runs_dir_is_used(tmp_path, monkeypatch):
    monkeypatch.delenv(s4.REPORT_ENV, raising=False)
    monkeypatch.setattr(s4, "RUNS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        s4.report_path()
    (tmp_path / "a.run-report.json").write_text("{}")
    assert s4.report_path().name == "a.run-report.json"

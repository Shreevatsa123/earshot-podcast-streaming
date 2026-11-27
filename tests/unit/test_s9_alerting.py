from types import SimpleNamespace

from acceptance import s9_alerting


class FakeApi:
    def __init__(self, *, reject=False):
        self.batches = []
        self.reject = reject

    def post(self, path, body):
        assert path == "/events"
        events = body["events"]
        self.batches.append(events)
        accepted = len(events) - int(self.reject)
        rejected = [{"index": 0, "reason": "INVALID_FIELD:event_id"}] if self.reject else []
        return SimpleNamespace(
            status=202,
            body={"accepted": accepted, "rejected": rejected},
        )


class FakeCloudWatch:
    def __init__(self):
        self.calls = 0
        self.queries = []

    def get_metric_data(self, **kwargs):
        self.calls += 1
        self.queries.append(kwargs["MetricDataQueries"][0])
        value = 0 if self.calls == 1 else 1
        return {"MetricDataResults": [{"Values": [value]}]}


class FakeContext:
    stage = "josh"

    def __init__(self, *, reject=False):
        self.api = FakeApi(reject=reject)
        self.cloudwatch = FakeCloudWatch()

    def client(self, service):
        assert service == "cloudwatch"
        return self.cloudwatch


def test_s9_sends_buffer_batches_and_waits_for_the_qoe_metric():
    ctx = FakeContext()

    measurement = s9_alerting.run(ctx)

    events = [event for batch in ctx.api.batches for event in batch]
    assert measurement.passed
    assert len(ctx.api.batches) == 5
    assert [len(batch) for batch in ctx.api.batches] == [25, 25, 25, 25, 20]
    assert len(events) == s9_alerting.EVENT_COUNT
    assert all(event["event_type"] == "buffer" for event in events)
    assert all(event["region"] == s9_alerting.REGION for event in events)
    assert all(event["user_id"] == "sim-acceptance-s9" for event in events)
    assert all("server_ts" not in event for event in events)
    assert len({event["event_id"] for event in events}) == s9_alerting.EVENT_COUNT
    assert ctx.cloudwatch.queries[0]["MetricStat"]["Metric"] == {
        "Namespace": "Earshot",
        "MetricName": "QoEAlertsSent",
        "Dimensions": [{"Name": "Stage", "Value": "josh"}],
    }


def test_s9_stops_if_ingest_rejects_a_buffer_batch():
    ctx = FakeContext(reject=True)

    measurement = s9_alerting.run(ctx)

    assert not measurement.passed
    assert "accepted 24/120" in measurement.measured
    assert len(ctx.api.batches) == 1
    assert ctx.cloudwatch.calls == 1

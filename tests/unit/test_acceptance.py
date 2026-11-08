"""The acceptance harness (M6-07). Runs without AWS: checks and clients are faked."""

import json
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from acceptance import harness, s10_cost
from acceptance.context import ApiClient
from acceptance.harness import Measurement, Status


def fake_check(criterion="S9", run=None):
    module = types.ModuleType(f"acceptance.fake_{criterion.lower()}")
    module.CRITERION, module.TITLE, module.OWNER, module.TARGET = criterion, "Fake", "M6", "target"
    module.run = run or (lambda ctx: Measurement(True, "ok"))
    return harness.as_check(module)


# ---- Discovery and selection -------------------------------------------------------------


def test_discovers_s1_to_s10_in_order():
    checks = harness.discover()
    assert [c.criterion for c in checks] == [f"S{n}" for n in range(1, 11)]
    assert all(c.title and c.owner and c.target for c in checks)


def test_select_only_some_criteria():
    checks = harness.discover()
    assert [c.criterion for c in harness.select(checks, ["s10", " S1 "])] == ["S1", "S10"]
    assert harness.select(checks, None) == checks
    with pytest.raises(ValueError, match="Unknown criteria"):
        harness.select(checks, ["S11"])


def test_a_check_must_declare_its_fields():
    module = types.ModuleType("acceptance.broken")
    module.CRITERION = "S3"
    with pytest.raises(ValueError, match="missing TITLE, OWNER, TARGET, run"):
        harness.as_check(module)


# ---- Running -------------------------------------------------------------------------------


def _raise(error):
    def run(ctx):
        raise error

    return run


@pytest.mark.parametrize(
    ("run", "status"),
    [
        (lambda ctx: Measurement(True, "0 wrong"), Status.PASS),
        (lambda ctx: Measurement(False, "3 wrong"), Status.FAIL),
        (_raise(NotImplementedError("M4: write this")), Status.NOT_IMPLEMENTED),
        (_raise(KeyError("no such table")), Status.ERROR),
        (lambda ctx: "not a Measurement", Status.ERROR),
    ],
)
def test_run_check_statuses(run, status):
    result = harness.run_check(fake_check(run=run), ctx=None)
    assert result.status is status
    assert result.criterion == "S9"


def test_exit_code_fails_only_on_fail_or_error():
    def results(*statuses):
        return [harness.run_check(fake_check(run=run), None) for run in statuses]

    passing = lambda ctx: Measurement(True, "ok")  # noqa: E731
    assert harness.exit_code(results(passing, _raise(NotImplementedError()))) == 0
    assert harness.exit_code(results(passing, lambda ctx: Measurement(False, "no"))) == 1
    assert harness.exit_code(results(_raise(RuntimeError("boom")))) == 1


# ---- Results file ------------------------------------------------------------------------


TABLE = "\n".join(
    [
        "intro text",
        harness.TABLE_START,
        *harness.TABLE_HEADER,
        "| S1 | One | t1 | M1 | PASS | recorded by hand | 2026-11-01 |",
        "| S2 | Two | t2 | M4 | NOT RUN |  |  |",
        harness.TABLE_END,
        "notes below",
    ]
)


def test_update_replaces_only_matching_rows():
    updated = harness.update_results_table(TABLE, {"S2": "| S2 | new |", "S11": "| S11 | added |"})
    lines = updated.splitlines()
    assert lines[0] == "intro text" and lines[-1] == "notes below"
    assert "| S1 | One | t1 | M1 | PASS | recorded by hand | 2026-11-01 |" in lines
    assert "| S2 | new |" in lines
    assert lines.index("| S11 | added |") == lines.index(harness.TABLE_END) - 1
    # Updating again with the same rows changes nothing.
    assert harness.update_results_table(updated, {"S2": "| S2 | new |"}) == updated


def test_update_needs_the_markers():
    with pytest.raises(ValueError, match="results:start"):
        harness.update_results_table("no table here", {"S1": "| S1 |"})


def test_cells_are_escaped():
    row = harness.render_row("S1", "a | b", "line1\nline2", "M1", "PASS")
    assert row == "| S1 | a \\| b | line1 line2 | M1 | PASS |  |  |"


def test_not_implemented_never_overwrites_a_row(tmp_path):
    path = tmp_path / "results.md"
    path.write_text(TABLE, encoding="utf-8")
    results = [
        harness.run_check(fake_check("S1", _raise(NotImplementedError())), None),
        harness.run_check(fake_check("S2", lambda ctx: Measurement(True, "p95 2.1 s")), None),
    ]
    assert harness.write_results_file(results, "prod", path) == ["S2"]
    text = path.read_text(encoding="utf-8")
    assert "recorded by hand" in text
    assert "| S2 | Fake | target | M6 | PASS | p95 2.1 s |" in text


def test_results_file_has_a_row_for_every_criterion():
    text = harness.RESULTS_FILE.read_text(encoding="utf-8")
    table = text[text.index(harness.TABLE_START) : text.index(harness.TABLE_END)]
    for check in harness.discover():
        assert f"| {check.criterion} | {check.title} |" in table, check.criterion


def test_write_report_saves_json(tmp_path):
    result = harness.run_check(fake_check(run=lambda ctx: Measurement(True, "ok", {"n": 1})), None)
    path = harness.write_report([result], "prod", tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["stage"] == "prod"
    assert saved["results"][0]["status"] == "PASS"
    assert saved["results"][0]["details"] == {"n": 1}


# ---- API client ----------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    seen: dict = {}

    def do_GET(self):  # noqa: N802 (http.server's naming)
        _Handler.seen = {k.lower(): v for k, v in self.headers.items()}
        status, body = (503, {"error": {"code": "PIPELINE_OFFLINE"}}) if self.path == "/down" else (200, {"rows": []})
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # keep test output quiet
        pass


@pytest.fixture
def api_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_api_client_sends_token_and_sim_user(api_server):
    client = ApiClient(api_server + "/", token=lambda: "tok123")
    response = client.get("/home", sim_user="sim-000042")
    assert response.status == 200
    assert response.body == {"rows": []}
    assert response.elapsed_ms >= 0
    assert _Handler.seen["authorization"] == "Bearer tok123"
    assert _Handler.seen["x-earshot-sim-user"] == "sim-000042"


def test_api_client_returns_errors_instead_of_raising(api_server):
    response = ApiClient(api_server, token=lambda: "tok").get("/down")
    assert response.status == 503
    assert response.body["error"]["code"] == "PIPELINE_OFFLINE"


def test_api_client_can_skip_auth(api_server):
    ApiClient(api_server, token=lambda: pytest.fail("no token for /health")).get("/home", auth=False)
    assert "authorization" not in _Handler.seen


# ---- S10 (the check M6 owns) -----------------------------------------------------------


class _Paginator:
    def __init__(self, pages):
        self._pages = pages

    def paginate(self, **_kwargs):
        return iter(self._pages)


class _Client:
    def __init__(self, pages=None):
        self._pages = pages or {}

    def get_paginator(self, operation):
        return _Paginator(self._pages.get(operation, [{}]))

    def list_delivery_streams(self, **_kwargs):
        return {"DeliveryStreamNames": []}

    def describe_addresses(self):
        return {"Addresses": []}

    def describe_stream_summary(self, StreamName):
        return {"StreamDescriptionSummary": {"StreamStatus": "ACTIVE", "OpenShardCount": 1}}


class _Ctx:
    def __init__(self, kinesis_streams=()):
        self._kinesis = _Client({"list_streams": [{"StreamNames": list(kinesis_streams)}]})

    def client(self, service):
        return self._kinesis if service == "kinesis" else _Client()


def test_s10_passes_when_nothing_hourly_is_left():
    measurement = s10_cost.run(_Ctx())
    assert measurement.passed
    assert measurement.measured.startswith("0 hourly-billed resources running")


def test_s10_fails_when_the_stream_is_still_up():
    measurement = s10_cost.run(_Ctx(kinesis_streams=["earshot-prod-events"]))
    assert not measurement.passed
    assert "Kinesis stream earshot-prod-events" in measurement.measured

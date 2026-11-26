"""S6 /home load test helpers and the S6 check (M6-06). No AWS or Locust needed."""

import random

import pytest

from acceptance import s6_api_perf
from acceptance.context import SIM_BOT_USERNAME
from load import home_load

# Shape of Locust's --csv *_stats.csv (only the columns we read matter).
HEADER = (
    '"Type","Name","Request Count","Failure Count","Median Response Time","Average Response Time",'
    '"Min Response Time","Max Response Time","Average Content Size","Requests/s","Failures/s",'
    '"50%","66%","75%","80%","90%","95%","98%","99%","99.9%","99.99%","100%"'
)


def stats(requests, failures, p95, name="Aggregated"):
    home = f'"GET","/home",{requests},{failures},120,140,60,900,2000,30.1,0.0,120,140,150,160,200,{p95},300,400,800,900,900'
    total = f'"","{name}",{requests},{failures},120,140,60,900,2000,30.1,0.0,120,140,150,160,200,{p95},300,400,800,900,900'
    return "\n".join([HEADER, home, total]) + "\n"


class FakeSsm:
    def __init__(self):
        self.calls = []

    def get_parameter(self, Name, WithDecryption=False):
        self.calls.append((Name, WithDecryption))
        return {"Parameter": {"Value": {"/earshot/prod/api/url": "https://api.example/"}.get(Name, f"value:{Name}")}}


def test_settings_come_from_the_stage_parameters():
    ssm = FakeSsm()
    settings = home_load.load_settings(ssm, "prod")
    assert settings.api_url == "https://api.example"  # trailing slash dropped
    assert settings.client_id == "value:/earshot/prod/cognito/sim-client-id"
    assert ("/earshot/prod/sim/password", True) in ssm.calls  # SecureString, decrypted


def test_sim_users_and_headers():
    rng = random.Random(1)
    users = {home_load.sim_user(rng) for _ in range(200)}
    assert all(u.startswith("sim-") and len(u) == 10 and int(u[4:]) < home_load.SIM_USERS for u in users)
    assert home_load.home_headers("tok", "sim-000042") == {
        "authorization": "Bearer tok",
        "x-earshot-sim-user": "sim-000042",
        "accept": "application/json",
    }


@pytest.mark.parametrize(
    ("requests", "failures", "p95", "passed"),
    [
        (9000, 0, 230, True),
        (9000, 89, 480, True),  # 0.99 % errors
        (9000, 90, 230, False),  # exactly 1 % is not < 1 %
        (9000, 0, 500, False),  # p95 must be under 500 ms
        (0, 0, "N/A", False),  # no requests at all
    ],
)
def test_parse_stats_and_pass_rule(requests, failures, p95, passed):
    result = home_load.parse_stats(stats(requests, failures, p95))
    assert (result.requests, result.failures) == (requests, failures)
    assert result.passed is passed


def test_parse_stats_needs_a_locust_file():
    with pytest.raises(ValueError, match="Aggregated"):
        home_load.parse_stats("a,b\n1,2\n")


def test_s6_reads_the_copied_stats_file(tmp_path, monkeypatch):
    path = tmp_path / "s6_stats.csv"
    path.write_text(stats(9000, 3, 230), encoding="utf-8")
    monkeypatch.setenv("S6_STATS_CSV", str(path))
    measurement = s6_api_perf.run(ctx=None)
    assert measurement.passed
    assert measurement.measured.startswith("p95 230 ms, errors 0.03 % (3/9000 requests)")
    assert measurement.details["p95_ms"] == 230


def test_s6_explains_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("S6_STATS_CSV", str(tmp_path / "missing.csv"))
    with pytest.raises(FileNotFoundError, match="runbook in tests/load/locustfile.py"):
        s6_api_perf.run(ctx=None)


def test_locustfile_signs_in_as_sim_bot_through_the_simulator():
    # The locustfile reuses the simulator's TokenProvider and SIM_USERNAME, which the
    # harness's own copy (SIM_BOT_USERNAME) is already checked against.
    text = (s6_api_perf.REPO_ROOT / "tests" / "load" / "locustfile.py").read_text(encoding="utf-8")
    assert "from simulator.__main__ import SIM_USERNAME" in text
    assert "from simulator.run import TokenProvider" in text
    assert SIM_BOT_USERNAME == "sim-bot@earshot.test"

"""S8 acceptance check (M2): flags flipped and restored, pass/fail counted. No AWS."""

import json
import types

import pytest

from acceptance import s8_degradation
from acceptance.context import ApiResponse

PARAM = "/earshot/test/flags"
ORIGINAL = {"recs_enabled": True, "recs_fault_injection": False}


class FakeSsm:
    def __init__(self):
        self.value = json.dumps(ORIGINAL)

    def get_parameter(self, Name):
        return {"Parameter": {"Value": self.value}}

    def put_parameter(self, Name, Value, Type, Overwrite):
        self.value = Value


class FakeApi:
    def __init__(self, ssm, reply):
        self.ssm, self.reply, self.flags_seen = ssm, reply, []

    def get(self, path, *, sim_user=None):
        assert path == "/home" and sim_user.startswith("sim-")
        self.flags_seen.append(json.loads(self.ssm.value))
        return self.reply(len(self.flags_seen))


def make_ctx(reply):
    ssm = FakeSsm()
    ctx = types.SimpleNamespace(cfg=types.SimpleNamespace(ssm_flags=PARAM), client=lambda name: ssm)
    ctx.api = FakeApi(ssm, reply)
    return ctx, ssm


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(s8_degradation.time, "sleep", lambda s: None)


def test_passes_when_every_home_is_degraded():
    ctx, ssm = make_ctx(lambda n: ApiResponse(200, {"degraded": True, "rows": [{}]}, 50.0))
    result = s8_degradation.run(ctx)
    assert result.passed and result.measured == "0 × 5xx, 20/20 degraded:true"
    assert all(f == {"recs_enabled": False, "recs_fault_injection": True} for f in ctx.api.flags_seen)
    assert json.loads(ssm.value) == ORIGINAL


@pytest.mark.parametrize(
    "bad", [ApiResponse(500, {"error": {"code": "INTERNAL"}}, 9.0), ApiResponse(200, {"degraded": False}, 9.0)]
)
def test_fails_on_a_5xx_or_a_response_that_isnt_degraded(bad):
    ctx, _ = make_ctx(lambda n: bad if n == 7 else ApiResponse(200, {"degraded": True}, 50.0))
    assert not s8_degradation.run(ctx).passed


def test_flags_are_restored_even_if_the_api_call_crashes():
    def crash(n):
        raise TimeoutError("no answer")

    ctx, ssm = make_ctx(crash)
    with pytest.raises(TimeoutError):
        s8_degradation.run(ctx)
    assert json.loads(ssm.value) == ORIGINAL

"""Tests for scripts/set_flag.py (M2-08), against an in-memory SSM parameter."""

from __future__ import annotations

import json

import pytest
import set_flag

PARAM = "/earshot/test/flags"


class FakeSsm:
    def __init__(self, flags: dict) -> None:
        self.value = json.dumps(flags)
        self.puts: list[dict] = []

    def get_parameter(self, Name: str) -> dict:
        return {"Parameter": {"Name": Name, "Value": self.value}}

    def put_parameter(self, **kwargs) -> None:
        self.puts.append(kwargs)
        self.value = kwargs["Value"]


def test_parse_changes_accepts_known_flags_any_case():
    assert set_flag.parse_changes(["recs_enabled=FALSE", "recs_fault_injection=true"]) == {
        "recs_enabled": False,
        "recs_fault_injection": True,
    }


@pytest.mark.parametrize("bad", ["recs=false", "recs_enabled", "recs_enabled=no", "recs_enabled="])
def test_parse_changes_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        set_flag.parse_changes([bad])


def test_change_writes_compact_json_and_keeps_other_flags():
    ssm = FakeSsm({"recs_enabled": True, "recs_fault_injection": False})
    before, after = set_flag.update_flags(ssm, PARAM, {"recs_fault_injection": True})

    assert before == {"recs_enabled": True, "recs_fault_injection": False}
    assert after == {"recs_enabled": True, "recs_fault_injection": True}
    assert ssm.puts == [
        {
            "Name": PARAM,
            "Value": '{"recs_enabled":true,"recs_fault_injection":true}',
            "Type": "String",
            "Overwrite": True,
        }
    ]


def test_no_write_when_showing_or_when_nothing_changes():
    ssm = FakeSsm({"recs_enabled": True})  # a missing flag must not trigger a write on "show"
    assert set_flag.update_flags(ssm, PARAM, {}) == ({"recs_enabled": True}, {"recs_enabled": True})

    ssm = FakeSsm({"recs_enabled": True, "recs_fault_injection": False})
    set_flag.update_flags(ssm, PARAM, {"recs_enabled": True})
    assert ssm.puts == []


def test_reset_restores_the_defaults():
    ssm = FakeSsm({"recs_enabled": False, "recs_fault_injection": True})
    _, after = set_flag.update_flags(ssm, PARAM, {}, reset=True)
    assert after == {"recs_enabled": True, "recs_fault_injection": False}
    assert json.loads(ssm.value) == after

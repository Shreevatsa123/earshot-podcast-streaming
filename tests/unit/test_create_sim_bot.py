"""Tests for scripts/create_sim_bot.py (M1-03), against in-memory SSM and Cognito fakes."""

from __future__ import annotations

import string

import create_sim_bot
import pytest

POOL = "us-east-1_TEST"
PARAM = "/earshot/test/sim/password"


class _Exceptions:
    class ParameterNotFound(Exception):
        pass

    class UserNotFoundException(Exception):
        pass


class FakeSsm:
    exceptions = _Exceptions

    def __init__(self, params: dict[str, str] | None = None) -> None:
        self.params = dict(params or {})
        self.puts: list[dict] = []

    def get_parameter(self, Name: str, WithDecryption: bool = False) -> dict:
        if Name not in self.params:
            raise _Exceptions.ParameterNotFound(Name)
        return {"Parameter": {"Name": Name, "Value": self.params[Name]}}

    def put_parameter(self, **kwargs) -> None:
        assert not (kwargs["Name"] in self.params and not kwargs["Overwrite"])
        self.puts.append(kwargs)
        self.params[kwargs["Name"]] = kwargs["Value"]


class FakeCognito:
    exceptions = _Exceptions

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.calls: list[str] = []

    def admin_get_user(self, UserPoolId: str, Username: str) -> dict:
        self.calls.append("get")
        if Username not in self.users:
            raise _Exceptions.UserNotFoundException(Username)
        return {"Username": Username}

    def admin_create_user(self, UserPoolId: str, Username: str, UserAttributes: list, MessageAction: str) -> None:
        self.calls.append("create")
        assert Username not in self.users
        self.users[Username] = {
            "attrs": {a["Name"]: a["Value"] for a in UserAttributes},
            "message": MessageAction,
            "groups": set(),
            "password": None,
            "permanent": False,
        }

    def admin_set_user_password(self, UserPoolId: str, Username: str, Password: str, Permanent: bool) -> None:
        self.calls.append("set_password")
        self.users[Username].update(password=Password, permanent=Permanent)

    def admin_add_user_to_group(self, UserPoolId: str, Username: str, GroupName: str) -> None:
        self.calls.append("add_group")
        self.users[Username]["groups"].add(GroupName)


def test_generated_password_meets_cognito_default_policy():
    for _ in range(50):
        pw = create_sim_bot.generate_password()
        assert len(pw) == create_sim_bot.PASSWORD_LENGTH
        assert any(c in string.ascii_lowercase for c in pw)
        assert any(c in string.ascii_uppercase for c in pw)
        assert any(c in string.digits for c in pw)
        assert any(c in create_sim_bot._SYMBOLS for c in pw)
    assert create_sim_bot.generate_password() != create_sim_bot.generate_password()


def test_creates_user_with_verified_email_permanent_password_and_group():
    cognito = FakeCognito()
    assert create_sim_bot.ensure_sim_bot(cognito, POOL, "Secret-1aA") is True

    user = cognito.users["sim-bot@earshot.test"]
    assert user["attrs"] == {"email": "sim-bot@earshot.test", "email_verified": "true"}
    assert user["message"] == "SUPPRESS"  # no invitation email to a fake address
    assert user["password"] == "Secret-1aA" and user["permanent"] is True
    assert user["groups"] == {"simulator"}


def test_second_run_repairs_without_creating_again():
    cognito = FakeCognito()
    create_sim_bot.ensure_sim_bot(cognito, POOL, "Old-1aA")
    cognito.calls.clear()

    assert create_sim_bot.ensure_sim_bot(cognito, POOL, "New-2bB") is False
    assert "create" not in cognito.calls
    assert cognito.users["sim-bot@earshot.test"]["password"] == "New-2bB"
    assert cognito.users["sim-bot@earshot.test"]["groups"] == {"simulator"}


def test_reads_existing_password_and_never_overwrites_it():
    ssm = FakeSsm({PARAM: "Stored-1aA"})
    assert create_sim_bot.read_or_create_password(ssm, PARAM, generate=True) == ("Stored-1aA", False)
    assert ssm.puts == []


def test_missing_password_needs_the_generate_flag():
    with pytest.raises(LookupError):
        create_sim_bot.read_or_create_password(FakeSsm(), PARAM, generate=False)


def test_generates_and_stores_a_secure_string_when_missing():
    ssm = FakeSsm()
    password, created = create_sim_bot.read_or_create_password(ssm, PARAM, generate=True)

    assert created is True
    assert ssm.puts == [{"Name": PARAM, "Value": password, "Type": "SecureString", "Overwrite": False}]


def test_username_matches_the_simulator_default():
    simulator_main = pytest.importorskip("simulator.__main__")
    assert create_sim_bot.SIM_USERNAME == simulator_main.SIM_USERNAME

"""scripts/account_check.py (M6-02/M6-03), tested with fake clients."""

import account_check


class FakeLambda:
    def __init__(self, limit=None, error=None):
        self._limit, self._error = limit, error

    def get_account_settings(self):
        if self._error:
            raise self._error
        return {"AccountLimit": {"ConcurrentExecutions": self._limit}}


class FakeQuotas:
    def __init__(self, applied=None, default=None):
        self._applied, self._default = applied, default
        self.calls = []

    def get_service_quota(self, ServiceCode, QuotaCode):
        self.calls.append(("applied", ServiceCode, QuotaCode))
        if self._applied is None:
            raise LookupError("NoSuchResourceException")
        return {"Quota": {"Value": self._applied}}

    def get_aws_default_service_quota(self, ServiceCode, QuotaCode):
        self.calls.append(("default", ServiceCode, QuotaCode))
        if self._default is None:
            raise LookupError("NoSuchResourceException")
        return {"Quota": {"Value": self._default}}


def test_good_limits_pass():
    text, code = account_check.check(FakeLambda(1000), FakeQuotas(applied=32.0))
    assert code == 0
    assert "1000 (OK)" in text and "32 (OK" in text


def test_low_limits_say_what_to_request():
    text, code = account_check.check(FakeLambda(10), FakeQuotas(applied=1.0))
    assert code == 1
    assert "10 (LOW). Request 1000" in text
    assert "TOO LOW" in text and "Running On-Demand Standard" in text


def test_falls_back_to_the_aws_default_quota():
    quotas = FakeQuotas(applied=None, default=5.0)
    _, code = account_check.check(FakeLambda(1000), quotas)
    assert code == 0
    assert [c[0] for c in quotas.calls] == ["applied", "default"]
    assert quotas.calls[0][1:] == account_check.EC2_STANDARD_VCPU_QUOTA


def test_unreadable_limits_exit_2():
    text, code = account_check.check(FakeLambda(error=PermissionError("AccessDenied")), FakeQuotas())
    assert code == 2
    assert text.count("couldn't read") == 2

import time

from shared import clock

# 2026-11-02T18:00:01.312Z
TS = 1_793_642_401_312


def test_now_ms_is_epoch_milliseconds():
    assert abs(clock.now_ms() - int(time.time() * 1000)) < 1000


def test_utc_date_and_minute():
    assert clock.utc_date(TS) == "2026-11-02"
    assert clock.utc_minute(TS) == "202611021800"

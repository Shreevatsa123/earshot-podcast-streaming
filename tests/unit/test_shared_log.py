import json

import pytest

from shared import log


def test_emit_metrics_uses_embedded_metric_format(monkeypatch, capsys):
    monkeypatch.setenv("STAGE", "priya")
    doc = log.emit_metrics({"EventsAccepted": 24, "EventsRejected": 1})
    printed = json.loads(capsys.readouterr().out)
    assert printed == doc
    directive = doc["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "Earshot"
    assert directive["Dimensions"] == [["Stage"]]
    assert [m["Name"] for m in directive["Metrics"]] == ["EventsAccepted", "EventsRejected"]
    assert doc["Stage"] == "priya"
    assert doc["EventsAccepted"] == 24


def test_emit_metrics_rejects_metrics_not_in_context():
    with pytest.raises(ValueError, match="CONTEXT"):
        log.emit_metrics({"PlaysPerUser": 1})


def test_emit_metrics_with_nothing_prints_nothing(capsys):
    log.emit_metrics({})
    assert capsys.readouterr().out == ""


def test_log_prints_one_json_line(capsys):
    log.log("batch done", records=100, failed=0)
    line = json.loads(capsys.readouterr().out)
    assert line["message"] == "batch done"
    assert line["level"] == "INFO"
    assert line["records"] == 100

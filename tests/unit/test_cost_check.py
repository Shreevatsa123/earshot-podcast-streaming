"""scripts/cost_check.py (M6-08), tested with fake boto3 clients (no AWS needed)."""

import cost_check


class FakePaginator:
    def __init__(self, pages):
        self._pages = pages

    def paginate(self, **_kwargs):
        return iter(self._pages)


class FakeClient:
    """Answers paginated calls from ``pages`` and plain calls from keyword methods."""

    def __init__(self, pages=None, **methods):
        self._pages = pages or {}
        for name, method in methods.items():
            setattr(self, name, method)

    def get_paginator(self, operation):
        return FakePaginator(self._pages.get(operation, [{}]))


def make_clients(**overrides):
    defaults = {
        "cloudformation": FakeClient(),
        "kinesis": FakeClient(),
        "firehose": FakeClient(list_delivery_streams=lambda **_: {"DeliveryStreamNames": []}),
        "ec2": FakeClient(describe_addresses=lambda: {"Addresses": []}),
        "elbv2": FakeClient(),
    }
    defaults.update(overrides)
    return cost_check.Clients(**defaults)


def busy_account():
    return make_clients(
        cloudformation=FakeClient(
            {
                "describe_stacks": [
                    {
                        "Stacks": [
                            {"StackName": "earshot-prod-base", "StackStatus": "UPDATE_COMPLETE"},
                            {"StackName": "earshot-prod-pipeline", "StackStatus": "CREATE_COMPLETE"},
                            {"StackName": "earshot-prod-servicecheck", "StackStatus": "ROLLBACK_COMPLETE"},
                        ]
                    }
                ]
            }
        ),
        kinesis=FakeClient(
            # Two pages, to prove pagination is followed.
            {"list_streams": [{"StreamNames": ["earshot-prod-events"]}, {"StreamNames": ["old-stream"]}]},
            describe_stream_summary=lambda StreamName: {
                "StreamDescriptionSummary": {
                    "StreamStatus": "ACTIVE" if StreamName == "earshot-prod-events" else "DELETING",
                    "StreamModeDetails": {"StreamMode": "PROVISIONED"},
                    "OpenShardCount": 1,
                }
            },
        ),
        firehose=FakeClient(
            list_delivery_streams=lambda **_: {
                "DeliveryStreamNames": ["earshot-prod-events-to-s3"],
                "HasMoreDeliveryStreams": False,
            }
        ),
        ec2=FakeClient(
            {
                "describe_instances": [
                    {
                        "Reservations": [
                            {
                                "Instances": [
                                    {
                                        "InstanceId": "i-run",
                                        "InstanceType": "t3.micro",
                                        "State": {"Name": "running"},
                                        "Tags": [{"Key": "project", "Value": "earshot"}],
                                    },
                                    {"InstanceId": "i-stop", "State": {"Name": "stopped"}},
                                    {"InstanceId": "i-gone", "State": {"Name": "terminated"}},
                                ]
                            }
                        ]
                    }
                ],
                "describe_nat_gateways": [
                    {
                        "NatGateways": [
                            {"NatGatewayId": "nat-1", "State": "available"},
                            {"NatGatewayId": "nat-old", "State": "deleted"},
                        ]
                    }
                ],
                "describe_volumes": [
                    {
                        "Volumes": [
                            {"VolumeId": "vol-loose", "State": "available", "Size": 8},
                            {"VolumeId": "vol-used", "State": "in-use", "Size": 8},
                        ]
                    }
                ],
            },
            describe_addresses=lambda: {"Addresses": [{"PublicIp": "203.0.113.7"}]},
        ),
        elbv2=FakeClient(
            {"describe_load_balancers": [{"LoadBalancers": [{"LoadBalancerName": "old-alb", "Type": "application"}]}]}
        ),
    )


def by_name(findings):
    return {f.name: f for f in findings}


def test_finds_everything_that_costs_money():
    findings, failures = cost_check.run_checks(busy_account())
    found = by_name(findings)
    assert failures == []

    hourly = {name for name, f in found.items() if f.hourly}
    assert hourly == {"earshot-prod-events", "i-run", "203.0.113.7", "nat-1", "old-alb"}

    leftovers = {name for name, f in found.items() if not f.hourly}
    assert leftovers == {
        "earshot-prod-pipeline",
        "earshot-prod-servicecheck",
        "old-stream",  # DELETING: no longer billing
        "earshot-prod-events-to-s3",
        "i-stop",
        "vol-loose",
    }
    # Persistent stacks, terminated instances, deleted NAT gateways and attached volumes are fine.
    assert not {"earshot-prod-base", "i-gone", "nat-old", "vol-used"} & found.keys()


def test_marks_earshot_resources_and_says_how_to_remove_session_stacks():
    found = by_name(cost_check.run_checks(busy_account())[0])
    assert found["i-run"].earshot  # by tag
    assert found["earshot-prod-events"].earshot  # by name
    assert not found["old-alb"].earshot
    assert "make pipeline-down STAGE=prod" in found["earshot-prod-pipeline"].detail
    assert "make service-check-down STAGE=prod" in found["earshot-prod-servicecheck"].detail


def test_exit_codes_and_report():
    findings, failures = cost_check.run_checks(busy_account())
    assert cost_check.exit_code(findings, failures) == 1
    text = cost_check.report(findings, failures)
    assert "BILLING EVERY HOUR" in text
    assert "5 hourly-billed resource(s) running" in text

    empty = cost_check.run_checks(make_clients())
    assert empty == ([], [])
    assert cost_check.exit_code(*empty) == 0
    assert "RESULT: OK" in cost_check.report(*empty)


def test_a_failing_check_is_reported_not_fatal():
    def denied(**_kwargs):
        raise PermissionError("AccessDenied")

    clients = make_clients(firehose=FakeClient(list_delivery_streams=denied))
    findings, failures = cost_check.run_checks(clients)
    assert findings == []
    assert len(failures) == 1 and failures[0].startswith("Firehose streams: PermissionError")
    assert cost_check.exit_code(findings, failures) == 2
    assert "COULDN'T CHECK" in cost_check.report(findings, failures)


def test_firehose_pagination_uses_the_last_name():
    calls = []

    def list_delivery_streams(**kwargs):
        calls.append(kwargs)
        if "ExclusiveStartDeliveryStreamName" not in kwargs:
            return {"DeliveryStreamNames": ["a"], "HasMoreDeliveryStreams": True}
        return {"DeliveryStreamNames": ["b"], "HasMoreDeliveryStreams": False}

    found = cost_check.check_firehose(FakeClient(list_delivery_streams=list_delivery_streams))
    assert [f.name for f in found] == ["a", "b"]
    assert calls[1]["ExclusiveStartDeliveryStreamName"] == "a"


def test_from_factory_builds_every_client():
    clients = cost_check.Clients.from_factory(lambda service: f"client:{service}")
    assert clients.kinesis == "client:kinesis"
    assert clients.elbv2 == "client:elbv2"


def test_main_without_boto3_exits_2(monkeypatch, capsys):
    import builtins

    real_import = builtins.__import__

    def no_boto3(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("no boto3")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_boto3)
    assert cost_check.main([]) == 2
    assert "make install" in capsys.readouterr().err

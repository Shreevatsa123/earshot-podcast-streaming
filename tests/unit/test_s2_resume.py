from acceptance import s2_resume
from acceptance.context import ApiResponse


class FakeApi:
    def __init__(self, *, position_offset=0, reject=False):
        self.events = []
        self.position_offset = position_offset
        self.reject = reject
        self.reads = 0

    def post(self, path, body):
        assert path == "/events"
        event = body["events"][0]
        self.events.append(event)
        if self.reject:
            return ApiResponse(202, {"accepted": 0, "rejected": [{"index": 0}]}, 1)
        return ApiResponse(202, {"accepted": 1, "rejected": []}, 1)

    def get(self, path, *, sim_user):
        event = self.events[-1]
        assert path == f"/progress/{event['episode_id']}"
        assert sim_user == event["user_id"]
        self.reads += 1
        return ApiResponse(
            200,
            {
                "episode_id": event["episode_id"],
                "position_sec": event["position_sec"] + self.position_offset,
                "completed": False,
                "updated_at": 1,
            },
            1,
        )


class FakeContext:
    def __init__(self, api):
        self.api = api


def test_s2_runs_twenty_unique_pause_trials_and_measures_progress():
    api = FakeApi()
    result = s2_resume.run(FakeContext(api))

    assert result.passed
    assert result.details["trials"] == 20
    assert len(api.events) == 20
    assert len({event["event_id"] for event in api.events}) == 20
    assert len({event["user_id"] for event in api.events}) == 20
    assert all(event["event_type"] == "pause" for event in api.events)
    assert all(event["user_id"].startswith("sim-s2-") for event in api.events)
    assert all("server_ts" not in event for event in api.events)


def test_s2_fails_when_progress_position_is_outside_tolerance():
    result = s2_resume.run(FakeContext(FakeApi(position_offset=3)))

    assert not result.passed
    assert len(result.details["position_mismatches"]) == s2_resume.TRIAL_COUNT


def test_s2_stops_when_ingest_rejects_an_event():
    api = FakeApi(reject=True)
    result = s2_resume.run(FakeContext(api))

    assert not result.passed
    assert result.details["completed_trials"] == 0
    assert result.details["trial"] == 1
    assert api.reads == 0

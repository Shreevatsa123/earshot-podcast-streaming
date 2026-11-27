from acceptance.s3_replay import _expected_plays, _expected_progress


def test_expected_progress_uses_latest_client_timestamp():
    older = {
        "user_id": "sim-test",
        "episode_id": "episode-1",
        "client_ts": 100,
        "position_sec": 20,
        "duration_sec": 100,
        "event_type": "pause",
    }
    newer = {**older, "client_ts": 200, "position_sec": 95, "event_type": "heartbeat"}

    assert _expected_progress([newer, older])[("sim-test", "episode-1")] == (
        200,
        95,
        100,
        True,
    )


def test_expected_plays_count_unique_event_ids_per_episode():
    events = [
        {"episode_id": "episode-1", "event_id": "play-1", "event_type": "play"},
        {"episode_id": "episode-1", "event_id": "play-1", "event_type": "play"},
        {"episode_id": "episode-1", "event_id": "play-2", "event_type": "play"},
        {"episode_id": "episode-2", "event_id": "pause-1", "event_type": "pause"},
    ]

    assert _expected_plays(events) == {"episode-1": 2}

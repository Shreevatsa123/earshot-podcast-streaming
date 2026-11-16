"""Virtual listeners and the playback events they produce (CONTEXT §6, §11).

- Users ``sim-000000 … sim-NNNNNN``, each with 2 favorite genres and a home region.
- Episode choice: a favorite genre most of the time, then Zipf popularity inside the genre
  (the same popularity order in every run, so trending has clear winners).
- 60 % of new sessions continue an unfinished episode, if the user has one.
- A session is ``play``, then ``heartbeat`` every 15 s with the odd ``seek`` or ``buffer``,
  and ends with ``pause`` or ``complete``.

Everything random comes from one ``random.Random``, so a seed reproduces a run's events.
"""

from __future__ import annotations

import bisect
import itertools
import json
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HEARTBEAT_SEC = 15
CONTINUE_PROBABILITY = 0.60
FAVORITE_GENRE_PROBABILITY = 0.85
ZIPF_EXPONENT = 1.1
#: Fixed seed for the popularity order, so it's the same in every run and every account.
POPULARITY_SEED = 650
REGION_WEIGHTS = {"us-east": 0.40, "us-west": 0.25, "eu-west": 0.20, "ap-south": 0.15}

# What happens at each step of a playing session (the rest are heartbeats).
P_PAUSE = 0.06
P_SEEK = 0.03
P_BUFFER = 0.02
#: Seconds between a pause/complete and the same user's next session.
SESSION_GAP_SEC = (30, 20 * 60)


@dataclass(frozen=True)
class Episode:
    show_id: str
    episode_id: str
    genre: str
    duration_sec: int


class Catalog:
    """The committed catalog snapshot (``contracts/samples/catalog.json``), with popularity weights."""

    def __init__(self, episodes: list[Episode]) -> None:
        if not episodes:
            raise ValueError("The catalog has no episodes")
        self.episodes = episodes
        self.genres = sorted({e.genre for e in episodes})
        order = random.Random(POPULARITY_SEED)
        self._by_genre: dict[str, list[Episode]] = {}
        self._cum_weights: dict[str, list[float]] = {}
        for genre in self.genres:
            ranked = sorted((e for e in episodes if e.genre == genre), key=lambda e: e.episode_id)
            order.shuffle(ranked)
            weights = [1.0 / (rank + 1) ** ZIPF_EXPONENT for rank in range(len(ranked))]
            self._by_genre[genre] = ranked
            self._cum_weights[genre] = list(itertools.accumulate(weights))

    @classmethod
    def load(cls, path: str | Path) -> Catalog:
        data = json.loads(Path(path).read_text())
        episodes = [
            Episode(str(e["show_id"]), str(e["episode_id"]), e["genre"], int(e["duration_sec"]))
            for e in data["episodes"]
        ]
        return cls(episodes)

    def pick(self, rng: random.Random, genre: str) -> Episode:
        """A Zipf-weighted episode from one genre."""
        cum = self._cum_weights[genre]
        index = bisect.bisect_left(cum, rng.random() * cum[-1])
        return self._by_genre[genre][min(index, len(cum) - 1)]


@dataclass
class Session:
    session_id: str
    episode: Episode
    position: int


@dataclass
class User:
    user_id: str
    favorite_genres: tuple[str, str]
    region: str
    unfinished: dict[str, tuple[Episode, int]] = field(default_factory=dict)
    session: Session | None = None


def new_uuid(rng: random.Random) -> str:
    """A UUID v4 drawn from ``rng`` (reproducible, unlike ``uuid.uuid4()``)."""
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def user_id(index: int) -> str:
    return f"sim-{index:06d}"


class Population:
    """``n`` virtual users and the state of what each one is listening to."""

    def __init__(self, catalog: Catalog, n_users: int, rng: random.Random) -> None:
        if n_users < 1:
            raise ValueError("Need at least 1 user")
        self.catalog = catalog
        self.rng = rng
        regions = list(REGION_WEIGHTS)
        weights = [REGION_WEIGHTS[r] for r in regions]
        self.users: list[User] = []
        for index in range(n_users):
            genres = rng.sample(catalog.genres, 2) if len(catalog.genres) >= 2 else catalog.genres * 2
            region = rng.choices(regions, weights)[0]
            self.users.append(User(user_id(index), (genres[0], genres[1]), region))

    # ---- choosing what to play -------------------------------------------------------

    def _start_session(self, user: User) -> Session:
        rng = self.rng
        if user.unfinished and rng.random() < CONTINUE_PROBABILITY:
            episode, position = user.unfinished[rng.choice(sorted(user.unfinished))]
        else:
            if rng.random() < FAVORITE_GENRE_PROBABILITY:
                genre = rng.choice(user.favorite_genres)
            else:
                genre = rng.choice(self.catalog.genres)
            episode = self.catalog.pick(rng, genre)
            saved = user.unfinished.get(episode.episode_id)
            position = saved[1] if saved else 0
        session = Session(new_uuid(rng), episode, min(position, episode.duration_sec))
        user.session = session
        return session

    # ---- events ----------------------------------------------------------------------

    def _event(
        self, user: User, session: Session, event_type: str, client_ts: int, region: str | None = None
    ) -> dict[str, Any]:
        return {
            "event_id": new_uuid(self.rng),
            "schema_version": 1,
            "user_id": user.user_id,
            "session_id": session.session_id,
            "show_id": session.episode.show_id,
            "episode_id": session.episode.episode_id,
            "genre": session.episode.genre,
            "event_type": event_type,
            "position_sec": session.position,
            "duration_sec": session.episode.duration_sec,
            "client_ts": client_ts,
            "region": region or user.region,
            "device": "sim",
        }

    def step(self, user: User, client_ts: int) -> tuple[dict[str, Any], float]:
        """Advance ``user`` by one action. Returns the event and seconds until their next one."""
        rng = self.rng
        session = user.session
        if session is None:
            session = self._start_session(user)
            return self._event(user, session, "play", client_ts), HEARTBEAT_SEC

        episode = session.episode
        roll = rng.random()
        if session.position + HEARTBEAT_SEC >= episode.duration_sec:
            session.position = episode.duration_sec
            event = self._event(user, session, "complete", client_ts)
            user.unfinished.pop(episode.episode_id, None)
            user.session = None
            return event, rng.uniform(*SESSION_GAP_SEC)
        if roll < P_PAUSE:
            session.position += rng.randint(1, HEARTBEAT_SEC)
            event = self._event(user, session, "pause", client_ts)
            user.unfinished[episode.episode_id] = (episode, session.position)
            user.session = None
            return event, rng.uniform(*SESSION_GAP_SEC)
        if roll < P_PAUSE + P_SEEK:
            session.position = rng.randint(0, max(0, episode.duration_sec - HEARTBEAT_SEC))
            return self._event(user, session, "seek", client_ts), rng.uniform(1, 5)
        if roll < P_PAUSE + P_SEEK + P_BUFFER:
            return self._event(user, session, "buffer", client_ts), rng.uniform(1, 5)
        session.position += HEARTBEAT_SEC
        return self._event(user, session, "heartbeat", client_ts), HEARTBEAT_SEC

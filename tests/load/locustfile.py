"""S6 load test: 50 users calling ``GET /home`` for 5 minutes (owner: M6 · tracker M6-06).

Spec: CONTEXT §14 S6: p95 < 500 ms and < 1 % errors at 50 concurrent users, run from the
simulator EC2 instance. Each Locust user acts as one random ``sim-NNNNNN`` user (header
``X-Earshot-Sim-User``, §7.2) and calls ``/home`` every 1-2 s: about 30 requests/s.

Before running it, prod needs the catalog (``make seed``) and the sim-bot user
(``scripts/create_sim_bot.py``). Post in the group chat before ``pipeline-up`` on prod.

Runbook (copy line by line):

1. From Codespaces: ``AWS_PROFILE=earshot-prod make pipeline-up STAGE=prod``
2. AWS console → EC2 → ``earshot-prod-simulator`` → Connect → Session Manager → Connect
3. On the instance::

       sudo -iu ec2-user
       mkdir -p /opt/earshot/tests/load && cd /opt/earshot/tests/load
       for f in home_load.py locustfile.py; do curl -fsSO https://raw.githubusercontent.com/Shreevatsa123/earshot-podcast-streaming/main/tests/load/$f; done
       python3.11 -m locust -f locustfile.py --headless -u 50 -r 10 -t 5m --csv s6 --only-summary
       cat s6_stats.csv

4. Copy the printed ``s6_stats.csv`` lines into ``tests/load/output/s6_stats.csv`` in
   Codespaces (git-ignored), then ``AWS_PROFILE=earshot-prod make acceptance STAGE=prod ONLY=S6``.
5. From Codespaces: ``AWS_PROFILE=earshot-prod make pipeline-down STAGE=prod``

The stage comes from ``EARSHOT_STAGE`` (the instance sets it in ``~/.bashrc``).
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # repo root, or /opt/earshot on the instance
for path in (HERE, ROOT, ROOT / "services"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import boto3  # noqa: E402
from locust import HttpUser, between, task  # noqa: E402

from home_load import home_headers, load_settings, sim_user  # noqa: E402
from shared import names  # noqa: E402
from simulator.__main__ import SIM_USERNAME  # noqa: E402
from simulator.run import TokenProvider  # noqa: E402

STAGE = os.environ.get("EARSHOT_STAGE", "prod")
_session = boto3.Session(region_name=os.environ.get("AWS_DEFAULT_REGION", names.REGION))
SETTINGS = load_settings(_session.client("ssm"), STAGE)
# One shared sim-bot token for every Locust user, refreshed before it expires.
TOKENS = TokenProvider(_session.client("cognito-idp"), SETTINGS.client_id, SIM_USERNAME, SETTINGS.password)
_rng = random.Random()


class HomeUser(HttpUser):
    host = SETTINGS.api_url
    wait_time = between(1, 2)

    def on_start(self) -> None:
        self.sim_user = sim_user(_rng)

    @task
    def home(self) -> None:
        headers = home_headers(TOKENS.get(), self.sim_user)
        with self.client.get("/home", headers=headers, name="/home", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                return
            if response.status_code == 401:
                TOKENS.get(force_refresh=True)
            response.failure(f"HTTP {response.status_code}")

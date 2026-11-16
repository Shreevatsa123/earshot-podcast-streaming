"""Earshot listener simulator (CONTEXT §11). Owner: M3.

Run from the repo root (or ``/opt/earshot`` on the simulator instance)::

    python -m simulator generate --out events.jsonl --users 200 --events 10000 --shuffle --dup-rate 0.10 --seed 7
    python -m simulator replay   --file events.jsonl --direct --stage <stage>
    python -m simulator run      --stage <stage> --users 2000 --rate 500 --duration 600 --seed 42

The simulator reuses ``services/shared`` (names and event validation), so it puts
``services/`` on ``sys.path`` here. The instance uses the same folder layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = ROOT / "contracts" / "samples" / "catalog.json"

_services = ROOT / "services"
if _services.is_dir() and str(_services) not in sys.path:
    sys.path.insert(0, str(_services))

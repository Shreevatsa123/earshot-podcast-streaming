#!/usr/bin/env python3
"""Check that every FEATURED episode's audio still plays (CONTEXT §8.1; demo runbook "day before").

Owner: M2 · Tracker: M2-02

    python scripts/catalog/check_featured.py

For each ``featured`` episode in ``contracts/samples/catalog.json``, requests the first KB
of its audio file and follows redirects, as the browser's ``<audio>`` element would.
"Plays" means the final URL is https (the site is https, so browsers block http audio)
and it serves audio. Exit code 1 if any fail: swap those for other episodes.
"""

from __future__ import annotations

import json
import sys
import urllib.request

from fetch_catalog import DEFAULT_OUT, USER_AGENT

#: Content types browsers play as audio (some CDNs label mp3 files as octet-stream).
AUDIO_TYPES = ("audio/", "application/octet-stream", "binary/octet-stream")


def audio_problem(url: str) -> str | None:
    """Why ``url`` wouldn't play in the browser, or None if it would."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-1023"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            final_url, content_type = response.geturl(), response.headers.get("Content-Type", "")
            response.read(1024)
    except Exception as err:  # HTTP errors, timeouts, TLS and DNS failures
        return f"{type(err).__name__}: {err}"
    if not final_url.startswith("https://"):
        return f"ends at a non-https URL: {final_url[:80]}"
    if not content_type.startswith(AUDIO_TYPES):
        return f"not audio: Content-Type {content_type!r}"
    return None


def main() -> int:
    catalog = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
    episodes = {episode["episode_id"]: episode for episode in catalog["episodes"]}
    featured = catalog.get("featured", [])
    failed = 0
    for item in featured:
        episode = episodes[item["episode_id"]]
        problem = audio_problem(episode["audio_url"])
        failed += problem is not None
        print(f"{'FAIL' if problem else 'ok  '}  {episode['genre']:11} {episode['title'][:60]}")
        if problem:
            print(f"      {problem}")
    print(f"{len(featured) - failed} of {len(featured)} featured episodes play")
    return 1 if failed or not featured else 0


if __name__ == "__main__":
    sys.exit(main())

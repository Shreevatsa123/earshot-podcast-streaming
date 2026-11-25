#!/usr/bin/env python3
"""Load the catalog snapshot into DynamoDB: Show, Episode and Featured items (CONTEXT §8.1).

Owner: M2 · Tracker: M2-03

    make seed STAGE=<stage>              # runs: python scripts/catalog/seed_catalog.py --stage <stage>

For prod: ``AWS_PROFILE=earshot-prod make seed STAGE=prod``, from a clean, up-to-date
``main``, after posting in the group chat (CONTEXT §5).

Reads ``contracts/samples/catalog.json`` and refuses to load it if ``check_catalog``
finds a problem or the ``featured`` list is missing. Safe to re-run: each item is a full
overwrite of the same key. It doesn't delete items of shows that left the snapshot.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SERVICES_DIR = str(Path(__file__).resolve().parents[2] / "services")
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)

from fetch_catalog import DEFAULT_OUT, check_catalog  # noqa: E402

from shared import names  # noqa: E402


def catalog_items(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Every §8.1 Show, Episode and Featured item for the snapshot."""
    items = [
        {
            "PK": f"SHOW#{show['show_id']}",
            "SK": "META",
            **show,
            "GSI1PK": f"GENRE#{show['genre']}",
            "GSI1SK": f"SHOW#{show['title'].lower()}",
        }
        for show in catalog["shows"]
    ]
    items += [
        {"PK": f"SHOW#{episode['show_id']}", "SK": f"EP#{episode['episode_id']}", **episode}
        for episode in catalog["episodes"]
    ]
    items.append({"PK": "FEATURED", "SK": "GLOBAL", "items": catalog["featured"]})
    return items


def seed(table: Any, catalog: dict[str, Any]) -> int:
    """Write every item with BatchWriteItem (25 per call, unprocessed items retried)."""
    items = catalog_items(catalog)
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
    return len(items)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the catalog snapshot into earshot-<stage>-main.")
    parser.add_argument("--stage", required=True, help="e.g. prod")
    args = parser.parse_args(argv)
    names.validate_stage(args.stage)

    catalog = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
    problems = check_catalog(catalog) + ([] if catalog.get("featured") else ["no featured list (M2-02)"])
    if problems:
        print("Not seeding; fix the catalog first:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    import boto3

    table = boto3.resource("dynamodb", region_name=names.REGION).Table(names.table_name(args.stage))
    try:
        count = seed(table, catalog)
    except table.meta.client.exceptions.ResourceNotFoundException:
        print(f"Table {table.name} doesn't exist. Deploy the base stack first.", file=sys.stderr)
        return 1
    print(
        f"Seeded {table.name}: {len(catalog['shows'])} shows, {len(catalog['episodes'])} episodes, "
        f"FEATURED with {len(catalog['featured'])} episodes ({count} items)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

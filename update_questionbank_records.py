#!/usr/bin/env python3
"""Update questionbank records in NocoDB.

- questionbank_name: remove .json suffix
- questionbank_name: replace leading R1/R3 with V1/V3
- type: set to "单词快反"
"""

import argparse
import sys
from typing import Dict, List, Tuple

import requests

sys.path.insert(0, "/Users/damien/.claude/skills/nocodb-manager/scripts")
from nocodb_api import NocoDBClient  # type: ignore

DEFAULT_TABLE_ID = "mcd5tmx0nqsgd3a"
DEFAULT_NAME_FIELD = "questionbank_name"
DEFAULT_TYPE_FIELD = "type"
DEFAULT_TYPE_VALUE = "单词快反"


def fetch_all_records(client: "NocoDBClient", table_id: str) -> List[Dict]:
    limit = 1000
    offset = 0
    all_records: List[Dict] = []

    while True:
        resp = client.get_records(table_id, limit=limit, offset=offset)
        records = resp.get("list") or []
        all_records.extend(records)

        page_info = resp.get("pageInfo") or {}
        is_last = page_info.get("isLastPage")
        if is_last or len(records) < limit:
            break
        offset += limit

    return all_records


def normalize_name(name: str) -> str:
    new_name = name
    if new_name.lower().endswith(".json"):
        new_name = new_name[:-5]

    if new_name.startswith("R1"):
        new_name = "V1" + new_name[2:]
    elif new_name.startswith("R3"):
        new_name = "V3" + new_name[2:]

    return new_name


def main() -> int:
    parser = argparse.ArgumentParser(description="Update questionbank records")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID)
    parser.add_argument("--name-field", default=DEFAULT_NAME_FIELD)
    parser.add_argument("--type-field", default=DEFAULT_TYPE_FIELD)
    parser.add_argument("--type-value", default=DEFAULT_TYPE_VALUE)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        client = NocoDBClient(base_url=args.base_url, token=args.token)
    except Exception as exc:
        print(f"ERROR: Failed to init NocoDB client: {exc}")
        return 1

    print("Fetching records...")
    records = fetch_all_records(client, args.table_id)

    updates: List[Tuple[int, Dict]] = []
    skipped_missing_id = 0

    for record in records:
        record_id = record.get("Id") or record.get("id")
        if record_id is None:
            skipped_missing_id += 1
            continue

        name = record.get(args.name_field)
        if not name:
            continue

        new_name = normalize_name(str(name))
        payload = {}

        if new_name != name:
            payload[args.name_field] = new_name

        if record.get(args.type_field) != args.type_value:
            payload[args.type_field] = args.type_value

        if payload:
            updates.append((record_id, payload))

    print(f"Total records: {len(records)}")
    print(f"Updates needed: {len(updates)}")
    if skipped_missing_id:
        print(f"Skipped (missing Id): {skipped_missing_id}")

    if args.dry_run:
        print("Dry run complete. No updates sent.")
        return 0

    errors: List[Tuple[int, str]] = []
    updated = 0

    for idx, (record_id, payload) in enumerate(updates, start=1):
        try:
            client.update_record(args.table_id, record_id, payload)
            updated += 1
        except Exception as exc:
            errors.append((record_id, str(exc)))

        if idx % 50 == 0:
            print(f"Updated {idx}/{len(updates)}...")

    print("\nSummary")
    print(f"Updated: {updated}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors (first 20):")
        for record_id, err in errors[:20]:
            print(f"  Id={record_id}: {err}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

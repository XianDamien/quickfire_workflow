#!/usr/bin/env python3
"""
Upload questionbank JSON files to NocoDB.

- questionbank_name: filename (with extension)
- questionbank_json: parsed JSON content
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import requests

NOCODB_SKILL_DIR = Path("/Users/damien/.claude/skills/nocodb-manager/scripts")

if not NOCODB_SKILL_DIR.exists():
    print(f"ERROR: NocoDB skill scripts not found at {NOCODB_SKILL_DIR}")
    sys.exit(1)

sys.path.insert(0, str(NOCODB_SKILL_DIR))

try:
    from nocodb_api import NocoDBClient  # type: ignore
except Exception as exc:
    print(f"ERROR: Failed to import NocoDBClient: {exc}")
    sys.exit(1)


DEFAULT_DIR = "/Users/damien/Desktop/Venture/quickfire_workflow/questionbank"
DEFAULT_TABLE_ID = "mcd5tmx0nqsgd3a"
DEFAULT_NAME_FIELD = "questionbank_name"
DEFAULT_JSON_FIELD = "questionbank_json"


def chunked(items: List[Dict], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


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


def build_existing_map(
    records: List[Dict],
    name_field: str,
) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    name_to_id: Dict[str, int] = {}
    duplicates: Dict[str, List[int]] = {}

    for record in records:
        name = record.get(name_field)
        if not name:
            continue
        record_id = record.get("Id") or record.get("id")
        if record_id is None:
            continue

        if name in name_to_id:
            duplicates.setdefault(name, []).append(record_id)
            continue

        name_to_id[name] = record_id

    return name_to_id, duplicates


def validate_fields(
    client: "NocoDBClient",
    table_id: str,
    required_fields: List[str],
) -> List[str]:
    fields = client.get_table_fields(table_id)
    columns = {f.get("column_name") for f in fields if f.get("column_name")}
    missing = [field for field in required_fields if field not in columns]
    return missing


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def batch_create(
    client: "NocoDBClient",
    table_id: str,
    records: List[Dict],
    chunk_size: int,
    create_errors: List[Tuple[str, str]],
) -> int:
    if not records:
        return 0

    created = 0
    url = f"{client.base_url}/api/v2/tables/{table_id}/records"

    for chunk in chunked(records, chunk_size):
        try:
            response = requests.post(url, headers=client.headers, json=chunk, timeout=60)
            response.raise_for_status()
            created += len(chunk)
        except Exception:
            # Fallback to per-record create for this chunk to isolate errors.
            for record in chunk:
                name = record.get(DEFAULT_NAME_FIELD) or "<unknown>"
                try:
                    client.create_record(table_id, record)
                    created += 1
                except Exception as exc:
                    create_errors.append((name, str(exc)))

    return created


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload questionbank JSON files to NocoDB"
    )
    parser.add_argument("--dir", default=DEFAULT_DIR, help="Directory of .json files")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID, help="NocoDB table id")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override NocoDB base URL (supports dashboard URL)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Override NocoDB API token (xc-token)",
    )
    parser.add_argument(
        "--name-field", default=DEFAULT_NAME_FIELD, help="Name field column"
    )
    parser.add_argument(
        "--json-field", default=DEFAULT_JSON_FIELD, help="JSON field column"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=200, help="Batch size for create"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and report without upload"
    )
    args = parser.parse_args()

    data_dir = Path(args.dir)
    if not data_dir.exists():
        print(f"ERROR: Directory not found: {data_dir}")
        return 1

    try:
        client = NocoDBClient(base_url=args.base_url, token=args.token)
    except Exception as exc:
        print(f"ERROR: Failed to init NocoDB client: {exc}")
        return 1

    missing = validate_fields(
        client, args.table_id, [args.name_field, args.json_field]
    )
    if missing:
        print(
            "ERROR: Missing required fields in table "
            f"{args.table_id}: {', '.join(missing)}"
        )
        return 1

    print("Fetching existing records...")
    existing_records = fetch_all_records(client, args.table_id)
    name_to_id, duplicates = build_existing_map(existing_records, args.name_field)

    if duplicates:
        print("WARNING: Duplicate names found in NocoDB (using first match):")
        for name, ids in list(duplicates.items())[:20]:
            print(f"  {name}: extra Ids={ids}")
        if len(duplicates) > 20:
            print(f"  ...and {len(duplicates) - 20} more")

    files = sorted(
        p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"
    )
    if not files:
        print("No .json files found to upload.")
        return 0

    invalid_json: List[Tuple[str, str]] = []
    to_create: List[Dict] = []
    to_update: List[Tuple[int, Dict]] = []

    for path in files:
        try:
            payload_json = load_json(path)
        except Exception as exc:
            invalid_json.append((path.name, str(exc)))
            continue

        payload = {
            args.name_field: path.name,
            args.json_field: payload_json,
        }

        existing_id = name_to_id.get(path.name)
        if existing_id is not None:
            to_update.append((existing_id, payload))
        else:
            to_create.append(payload)

    print(f"Total files: {len(files)}")
    print(f"Valid JSON: {len(files) - len(invalid_json)}")
    print(f"To create: {len(to_create)}")
    print(f"To update: {len(to_update)}")
    print(f"Invalid JSON: {len(invalid_json)}")

    if args.dry_run:
        print("Dry run complete. No records were created or updated.")
        if invalid_json:
            print("Invalid JSON files:")
            for name, err in invalid_json:
                print(f"  {name}: {err}")
        return 0

    updated = 0
    update_errors: List[Tuple[str, str]] = []

    if to_update:
        print("Updating existing records...")
        for record_id, payload in to_update:
            name = payload.get(args.name_field) or "<unknown>"
            try:
                client.update_record(args.table_id, record_id, payload)
                updated += 1
            except Exception as exc:
                update_errors.append((name, str(exc)))

    create_errors: List[Tuple[str, str]] = []
    created = 0
    if to_create:
        print("Creating new records...")
        created = batch_create(
            client, args.table_id, to_create, args.chunk_size, create_errors
        )

    print("\nSummary")
    print(f"Created: {created}")
    print(f"Updated: {updated}")
    print(f"Invalid JSON: {len(invalid_json)}")
    print(f"Create errors: {len(create_errors)}")
    print(f"Update errors: {len(update_errors)}")

    if invalid_json:
        print("\nInvalid JSON files:")
        for name, err in invalid_json:
            print(f"  {name}: {err}")

    if create_errors:
        print("\nCreate errors:")
        for name, err in create_errors[:50]:
            print(f"  {name}: {err}")
        if len(create_errors) > 50:
            print(f"  ...and {len(create_errors) - 50} more")

    if update_errors:
        print("\nUpdate errors:")
        for name, err in update_errors[:50]:
            print(f"  {name}: {err}")
        if len(update_errors) > 50:
            print(f"  ...and {len(update_errors) - 50} more")

    if create_errors or update_errors:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

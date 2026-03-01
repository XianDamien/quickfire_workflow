#!/usr/bin/env python3
"""NocoDB Questionbank Manager.

Subcommands:
  upload  - Upload questionbank JSON files to NocoDB (upsert)
  update  - Batch normalize record names and set type fields
  list    - List all questionbank records
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

sys.path.insert(0, str(Path.home() / ".claude/skills/nocodb-manager/scripts"))
from nocodb_api import NocoDBClient  # type: ignore

DEFAULT_TABLE_ID = "mcd5tmx0nqsgd3a"
NAME_FIELD = "questionbank_name"
JSON_FIELD = "questionbank_json"
TYPE_FIELD = "type"
TYPE_VALUE = "单词快反"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def fetch_all_records(client: NocoDBClient, table_id: str) -> List[Dict]:
    """Paginated fetch of all table records."""
    limit = 1000
    offset = 0
    all_records: List[Dict] = []
    while True:
        resp = client.get_records(table_id, limit=limit, offset=offset)
        batch = resp.get("list") or []
        all_records.extend(batch)
        page_info = resp.get("pageInfo") or {}
        if page_info.get("isLastPage") or len(batch) < limit:
            break
        offset += limit
    return all_records


def record_id(record: Dict) -> Optional[int]:
    return record.get("Id") or record.get("id")


def chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def print_errors(label: str, errors: list, limit: int = 50):
    if not errors:
        return
    print(f"\n{label}:")
    for item in errors[:limit]:
        if isinstance(item, tuple) and len(item) == 2:
            print(f"  {item[0]}: {item[1]}")
    if len(errors) > limit:
        print(f"  ...and {len(errors) - limit} more")


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------

def _build_name_map(
    records: List[Dict],
) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    name_to_id: Dict[str, int] = {}
    duplicates: Dict[str, List[int]] = {}
    for rec in records:
        name = rec.get(NAME_FIELD)
        rid = record_id(rec)
        if not name or rid is None:
            continue
        if name in name_to_id:
            duplicates.setdefault(name, []).append(rid)
        else:
            name_to_id[name] = rid
    return name_to_id, duplicates


def _batch_create(
    client: NocoDBClient,
    table_id: str,
    records: List[Dict],
    chunk_size: int,
    errors: List[Tuple[str, str]],
) -> int:
    if not records:
        return 0
    created = 0
    url = f"{client.base_url}/api/v2/tables/{table_id}/records"
    for chunk in chunked(records, chunk_size):
        try:
            resp = requests.post(url, headers=client.headers, json=chunk, timeout=60)
            resp.raise_for_status()
            created += len(chunk)
        except Exception:
            for rec in chunk:
                name = rec.get(NAME_FIELD) or "<unknown>"
                try:
                    client.create_record(table_id, rec)
                    created += 1
                except Exception as exc:
                    errors.append((name, str(exc)))
    return created


def cmd_upload(args: argparse.Namespace, client: NocoDBClient) -> int:
    table_id = args.table_id
    data_dir = Path(args.dir)
    if not data_dir.exists():
        print(f"ERROR: Directory not found: {data_dir}")
        return 1

    # Validate required columns exist
    fields = client.get_table_fields(table_id)
    columns = {f.get("column_name") for f in fields if f.get("column_name")}
    missing = [c for c in (NAME_FIELD, JSON_FIELD) if c not in columns]
    if missing:
        print(f"ERROR: Missing columns in table: {', '.join(missing)}")
        return 1

    print("Fetching existing records...")
    existing = fetch_all_records(client, table_id)
    name_to_id, duplicates = _build_name_map(existing)

    if duplicates:
        print("WARNING: Duplicate names (using first match):")
        for name, ids in list(duplicates.items())[:20]:
            print(f"  {name}: extra Ids={ids}")

    files = sorted(
        p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"
    )
    if not files:
        print("No .json files found.")
        return 0

    invalid: List[Tuple[str, str]] = []
    to_create: List[Dict] = []
    to_update: List[Tuple[int, Dict]] = []

    for path in files:
        try:
            with path.open("r", encoding="utf-8") as f:
                content = json.load(f)
        except Exception as exc:
            invalid.append((path.name, str(exc)))
            continue

        payload = {NAME_FIELD: path.name, JSON_FIELD: content}
        eid = name_to_id.get(path.name)
        if eid is not None:
            to_update.append((eid, payload))
        else:
            to_create.append(payload)

    print(f"Total files: {len(files)}")
    print(f"Valid JSON: {len(files) - len(invalid)}")
    print(f"To create: {len(to_create)}")
    print(f"To update: {len(to_update)}")
    print(f"Invalid JSON: {len(invalid)}")

    if args.dry_run:
        print("Dry run complete.")
        print_errors("Invalid JSON files", invalid)
        return 0

    updated = 0
    update_errors: List[Tuple[str, str]] = []
    if to_update:
        print("Updating existing records...")
        for rid, payload in to_update:
            name = payload.get(NAME_FIELD) or "<unknown>"
            try:
                client.update_record(table_id, rid, payload)
                updated += 1
            except Exception as exc:
                update_errors.append((name, str(exc)))

    create_errors: List[Tuple[str, str]] = []
    created = 0
    if to_create:
        print("Creating new records...")
        created = _batch_create(
            client, table_id, to_create, args.chunk_size, create_errors
        )

    print(f"\nCreated: {created}, Updated: {updated}")
    print_errors("Invalid JSON", invalid)
    print_errors("Create errors", create_errors)
    print_errors("Update errors", update_errors)
    return 1 if (create_errors or update_errors) else 0


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    n = name
    if n.lower().endswith(".json"):
        n = n[:-5]
    if n.startswith("R1"):
        n = "V1" + n[2:]
    elif n.startswith("R3"):
        n = "V3" + n[2:]
    return n


def cmd_update(args: argparse.Namespace, client: NocoDBClient) -> int:
    table_id = args.table_id
    print("Fetching records...")
    records = fetch_all_records(client, table_id)

    updates: List[Tuple[int, Dict]] = []
    skipped = 0
    for rec in records:
        rid = record_id(rec)
        if rid is None:
            skipped += 1
            continue
        name = rec.get(NAME_FIELD)
        if not name:
            continue
        payload: Dict = {}
        new_name = _normalize_name(str(name))
        if new_name != name:
            payload[NAME_FIELD] = new_name
        if rec.get(TYPE_FIELD) != args.type_value:
            payload[TYPE_FIELD] = args.type_value
        if payload:
            updates.append((rid, payload))

    print(f"Total: {len(records)}, Updates needed: {len(updates)}")
    if skipped:
        print(f"Skipped (no Id): {skipped}")

    if args.dry_run:
        print("Dry run complete.")
        return 0

    errors: List[Tuple[int, str]] = []
    ok = 0
    for idx, (rid, payload) in enumerate(updates, 1):
        try:
            client.update_record(table_id, rid, payload)
            ok += 1
        except Exception as exc:
            errors.append((rid, str(exc)))
        if idx % 50 == 0:
            print(f"Progress: {idx}/{len(updates)}")

    print(f"\nUpdated: {ok}, Errors: {len(errors)}")
    if errors:
        for rid, err in errors[:20]:
            print(f"  Id={rid}: {err}")
    return 1 if errors else 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace, client: NocoDBClient) -> int:
    table_id = args.table_id
    records = fetch_all_records(client, table_id)
    print(f"Total records: {len(records)}")
    for rec in records[: args.limit]:
        rid = record_id(rec)
        name = rec.get(NAME_FIELD, "<no name>")
        rtype = rec.get(TYPE_FIELD, "<no type>")
        print(f"  Id={rid}  {name}  type={rtype}")
    if len(records) > args.limit:
        print(f"  ... and {len(records) - args.limit} more")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="NocoDB Questionbank Manager")
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID)
    parser.add_argument("--base-url", default=None, help="Override NocoDB base URL")
    parser.add_argument("--token", default=None, help="Override NocoDB API token")

    sub = parser.add_subparsers(dest="command", required=True)

    p_upload = sub.add_parser("upload", help="Upload JSON files to NocoDB")
    p_upload.add_argument("--dir", default="questionbank", help="JSON files directory")
    p_upload.add_argument("--chunk-size", type=int, default=200, help="Batch size")
    p_upload.add_argument("--dry-run", action="store_true")

    p_update = sub.add_parser("update", help="Normalize names & set type")
    p_update.add_argument("--type-value", default=TYPE_VALUE)
    p_update.add_argument("--dry-run", action="store_true")

    p_list = sub.add_parser("list", help="List questionbank records")
    p_list.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()

    try:
        client = NocoDBClient(
            base_url=getattr(args, "base_url", None),
            token=getattr(args, "token", None),
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    handlers = {"upload": cmd_upload, "update": cmd_update, "list": cmd_list}
    return handlers[args.command](args, client)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Quick MongoDB backend check for Anonymous Studio."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _resolve_db_name(uri: str) -> str:
    # Keep behavior aligned with store.mongo.MongoStore.
    return (uri.split("/")[-1].split("?")[0].strip() or "anon_studio")


def _fmt_entity_counts(counts: Any) -> str:
    if not isinstance(counts, dict) or not counts:
        return "{}"
    parts = [f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))]
    return "{ " + ", ".join(parts) + " }"


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(".env")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Validate MongoDB connectivity and core app collections.")
    parser.add_argument(
        "--uri",
        default=os.environ.get("MONGODB_URI", "").strip(),
        help="Mongo URI (defaults to MONGODB_URI env var).",
    )
    args = parser.parse_args()

    uri = (args.uri or "").strip()
    if not uri:
        print("ERROR: MONGODB_URI is empty. Set it or pass --uri.", file=sys.stderr)
        return 2

    try:
        from pymongo import MongoClient
    except Exception as exc:
        print(f"ERROR: pymongo unavailable: {exc}", file=sys.stderr)
        return 2

    db_name = _resolve_db_name(uri)
    print(f"URI: {uri}")
    print(f"DB:  {db_name}")

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[db_name]
        ping = db.command("ping")
        print(f"Ping: {ping}")

        collections = sorted(db.list_collection_names())
        print(f"Collections ({len(collections)}): {collections}")

        sessions = db["pii_sessions"]
        count = sessions.count_documents({})
        print(f"pii_sessions count: {count}")

        latest = sessions.find_one(
            {},
            projection={
                "_id": 1,
                "title": 1,
                "created_at": 1,
                "entity_counts": 1,
                "operator": 1,
                "source_type": 1,
            },
            sort=[("created_at", -1)],
        )
        if latest:
            print("latest pii_session:")
            print(f"  id:         {latest.get('_id')}")
            print(f"  title:      {latest.get('title')}")
            print(f"  created_at: {latest.get('created_at')}")
            print(f"  operator:   {latest.get('operator')}")
            print(f"  source:     {latest.get('source_type')}")
            print(f"  entities:   {_fmt_entity_counts(latest.get('entity_counts'))}")
        else:
            print("latest pii_session: <none>")
        return 0
    except Exception as exc:
        print(f"ERROR: Mongo check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

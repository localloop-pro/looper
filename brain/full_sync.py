"""F2.2 — Nightly full sync: SQLite → TypeDB.

Reads all active businesses from the LOOPER SQLite database and upserts each
into TypeDB.  Intended to run as a Coolify Scheduled Task (`0 3 * * *`).

Usage:
    python brain/full_sync.py [--db-url sqlite:///data/looper.db]
                              [--host localhost:1729]
                              [--typedb-db localloop]

Environment variables override CLI defaults:
    LOOPER_DB_URL   — SQLite DB path (matches backend/main.py)
    TYPEDB_ADDRESS  — TypeDB host:port
    TYPEDB_DB       — TypeDB database name
    TYPEDB_ENABLED  — must be "true" for sync to run

The script is safe to re-run: sync_business() is idempotent.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root: `python brain/full_sync.py`
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = os.getenv(
    "LOOPER_DB_URL",
    f"sqlite:///{Path(__file__).parent.parent / 'backend' / 'data' / 'looper.db'}",
)
DEFAULT_HOST = os.getenv("TYPEDB_ADDRESS", "localhost:1729")
DEFAULT_TYPEDB_DB = os.getenv("TYPEDB_DB", "localloop")


def run_full_sync(db_url: str, typedb_host: str, typedb_db: str) -> None:
    # Temporarily override the envs that sync.py reads so we can pass
    # non-default values in from the CLI.
    os.environ["TYPEDB_ADDRESS"] = typedb_host
    os.environ["TYPEDB_DB"] = typedb_db
    os.environ["TYPEDB_ENABLED"] = "true"

    from sync import sync_business  # type: ignore[import]

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("ERROR: sqlalchemy not installed. Run: pip install sqlalchemy", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, hybrid_card_id, name, category, lat, lng, is_active "
            "FROM businesses"
        )).fetchall()

    if not rows:
        logger.info("No businesses found in SQLite — nothing to sync")
        return

    logger.info("Full sync: %d businesses to upsert", len(rows))
    ok = err = 0
    for row in rows:
        hid = row[1] if row[1] else f"seed:{row[0]}"
        success = sync_business(
            hybrid_card_id=hid,
            name=row[2] or "",
            category=row[3] or "other",
            lat=row[4],
            lng=row[5],
            is_active=bool(row[6]),
        )
        if success:
            ok += 1
        else:
            logger.warning("  sync failed for %s", row[0])
            err += 1

    logger.info("Full sync complete: %d ok, %d errors", ok, err)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LOOPER brain full sync (SQLite → TypeDB)")
    p.add_argument("--db-url", default=DEFAULT_DB_URL)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--typedb-db", default=DEFAULT_TYPEDB_DB)
    args = p.parse_args()
    run_full_sync(args.db_url, args.host, args.typedb_db)

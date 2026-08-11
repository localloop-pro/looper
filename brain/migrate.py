"""TypeDB schema migration runner for the LOOPER brain.

Applies *.tql files from brain/schema/ in alphabetical order (001_geo.tql
before 002_business.tql, etc.).  A .applied_migrations text file in this
directory tracks which files have already been applied — safe to re-run.

Usage:
    python brain/migrate.py [--host localhost:1729] [--db localloop]

Environment:
    TYPEDB_ADDRESS — overrides --host default
    TYPEDB_DB      — overrides --db default

Package: pip install typedb-driver
Verify the version with `pip index versions typedb-driver` and pin it in
requirements-brain.txt; record the pinned version in .SEED/decisions.md.
"""
import argparse
import os
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).parent / "schema"
APPLIED_LOG = Path(__file__).parent / ".applied_migrations"
DEFAULT_HOST = os.getenv("TYPEDB_ADDRESS", "localhost:1729")
DEFAULT_DB = os.getenv("TYPEDB_DB", "localloop")


def _applied() -> set[str]:
    if not APPLIED_LOG.exists():
        return set()
    return {line.strip() for line in APPLIED_LOG.read_text().splitlines() if line.strip()}


def _mark_applied(filename: str) -> None:
    with APPLIED_LOG.open("a") as fh:
        fh.write(filename + "\n")


def migrate(host: str, db_name: str, dry_run: bool = False) -> None:
    try:
        from typedb.driver import TypeDB, SessionType, TransactionType  # type: ignore[import]
    except ImportError:
        print(
            "ERROR: typedb-driver not installed.\n"
            "  pip install typedb-driver\n"
            "  (pin exact version — see README.md and .SEED/decisions.md)",
            file=sys.stderr,
        )
        sys.exit(1)

    schema_files = sorted(SCHEMA_DIR.glob("*.tql"))
    if not schema_files:
        print(f"No .tql files found in {SCHEMA_DIR}")
        return

    applied = _applied()
    pending = [f for f in schema_files if f.name not in applied]
    if not pending:
        print("All migrations already applied — nothing to do.")
        return

    if dry_run:
        for f in pending:
            print(f"  would apply: {f.name}")
        return

    print(f"Connecting to TypeDB at {host} ...")
    with TypeDB.core_driver(host) as driver:
        if not driver.databases.contains(db_name):
            print(f"  creating database '{db_name}'")
            driver.databases.create(db_name)
        else:
            print(f"  database '{db_name}' exists")

        with driver.session(db_name, SessionType.SCHEMA) as session:
            for schema_file in pending:
                print(f"  applying: {schema_file.name} ...", end=" ", flush=True)
                schema_str = schema_file.read_text()
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.define(schema_str)
                    tx.commit()
                _mark_applied(schema_file.name)
                print("done")

    print("Migration complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LOOPER TypeDB schema migrator")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--dry-run", action="store_true", help="list pending migrations without applying")
    args = p.parse_args()
    migrate(args.host, args.db, dry_run=args.dry_run)

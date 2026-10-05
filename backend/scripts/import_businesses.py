#!/usr/bin/env python3
"""Import owner-verified businesses from a CSV (looper#74).

Usage (dry run first, always against a COPY of the DB):
    python backend/scripts/import_businesses.py --csv businesses.csv --db sqlite:////path/to/copy.db
    python backend/scripts/import_businesses.py --csv businesses.csv --db sqlite:////path/to/copy.db --apply

Dry run is the default: it prints what it would insert, skip or reject and
writes nothing. Only ``--apply`` commits, in ONE transaction for the run.

CSV columns (header row required, template: docs/templates/businesses.csv):
    name, category, suburb, address, lat, lng, phone, website, description
Required: name, category, suburb, lat, lng. lat/lng must be finite and inside
a sanity box around Australia; website must be https:// or empty. A bad row
is rejected with a reason and the rest carry on.

Never updates, overwrites or deletes: a row whose accent-folded
(name, suburb) already exists in the DB (any source, active or not, e.g. a
``hybrid_card`` row) or earlier in the same CSV is skipped. Inserted rows get
``source="owner_verified"``, ``is_verified=False``, ``is_active=True`` and no
``hybrid_card_id``. No schema change: the DB must already have a
``businesses`` table, and a missing SQLite file is never created (exit 2).

Exit codes: 0 = run finished (check the summary for rejects), 2 = could not
run (bad arguments, missing file/table, wrong CSV header).
"""
from __future__ import annotations

import argparse
import csv
import math
import pathlib
import sys
from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
# Only the ORM class and the folding helper are used. models' own engine
# (LOOPER_DB_URL) is never touched: every read and write goes to --db.
from models import Business, fold_accents  # noqa: E402

COLUMNS = ["name", "category", "suburb", "address", "lat", "lng", "phone", "website", "description"]
REQUIRED = ["name", "category", "suburb", "lat", "lng"]
# Mainland Australia plus Tasmania, with a margin. Catches swapped lat/lng,
# a missing minus sign and 0,0 placeholders. (Lord Howe and Norfolk Island
# fall outside on purpose; widen this if the owner ever needs them.)
LAT_RANGE = (-44.0, -9.0)
LNG_RANGE = (112.0, 154.5)
# The String column lengths in models.Business; SQLite would not enforce them.
MAX_LEN = {"name": 200, "category": 100, "suburb": 100, "address": 500,
           "phone": 20, "website": 500}
SOURCE = "owner_verified"


def dedupe_key(name: str | None, suburb: str | None) -> tuple[str, str]:
    """Accent-folded, lowercased, whitespace-collapsed (name, suburb)."""
    def norm(v: str | None) -> str:
        return " ".join((fold_accents(v) or "").split())
    return norm(name), norm(suburb)


def _coord(raw: str, label: str, lo: float, hi: float) -> tuple[float | None, str | None]:
    try:
        value = float(raw)
    except ValueError:
        return None, f"{label} is not a number"
    if not math.isfinite(value):
        return None, f"{label} must be a finite number"
    if not lo <= value <= hi:
        return None, f"{label} {value} is outside Australia ({lo} to {hi})"
    return value, None


def _https_with_host(raw: str) -> bool:
    # urlparse raises ValueError on a bad bracketed host ("https://[bad");
    # netloc alone accepts hostless "https://:443", so require .hostname.
    try:
        url = urlparse(raw)
        return url.scheme.lower() == "https" and bool(url.hostname)
    except ValueError:
        return False


def validate(row: dict[str, str]) -> tuple[dict | None, str | None]:
    """Return (clean fields, None) or (None, reason)."""
    clean = {c: (row.get(c) or "").strip() for c in COLUMNS}
    missing = [c for c in REQUIRED if not clean[c]]
    if missing:
        return None, "missing " + ", ".join(missing)
    for col, limit in MAX_LEN.items():
        if len(clean[col]) > limit:
            return None, f"{col} is longer than {limit} characters"
    lat, err = _coord(clean["lat"], "lat", *LAT_RANGE)
    if err:
        return None, err
    lng, err = _coord(clean["lng"], "lng", *LNG_RANGE)
    if err:
        return None, err
    if clean["website"] and not _https_with_host(clean["website"]):
        return None, "website must start with https:// and name a host (or be empty)"
    out = {c: (clean[c] or None) for c in COLUMNS}
    out["lat"], out["lng"] = lat, lng
    return out, None


def _sqlite_file_missing(db_url: str) -> str | None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite"):
        return None
    if not url.database or url.database == ":memory:":
        return "an in-memory SQLite DB has no businesses table"
    if not pathlib.Path(url.database).is_file():
        return f"SQLite file not found: {url.database} (nothing was created)"
    return None


def run(csv_path: pathlib.Path, db_url: str, apply: bool, out=sys.stdout) -> dict:
    def say(msg: str) -> None:
        print(msg, file=out)

    try:
        problem = _sqlite_file_missing(db_url)
    except ArgumentError as exc:
        raise SystemExit(f"error: bad --db URL: {exc}")
    if problem:
        raise SystemExit(f"error: {problem}")
    if not csv_path.is_file():
        raise SystemExit(f"error: CSV not found: {csv_path}")

    engine = create_engine(db_url)
    try:
        if not inspect(engine).has_table(Business.__tablename__):
            raise SystemExit("error: the DB has no businesses table (this script never creates one)")

        # utf-8-sig: Excel and Numbers often write a byte-order mark.
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = [h.strip().lower() for h in (reader.fieldnames or [])]
            absent = [c for c in REQUIRED if c not in header]
            if absent:
                raise SystemExit("error: CSV header is missing " + ", ".join(absent)
                                 + f" (expected: {','.join(COLUMNS)})")
            reader.fieldnames = header
            rows = list(reader)

        counts = {"inserted": 0, "skipped_duplicate": 0, "rejected": 0}
        session = sessionmaker(bind=engine)()
        try:
            seen = {dedupe_key(n, s) for n, s in session.query(Business.name, Business.suburb)}
            # Line 1 is the header, so the first data row is line 2.
            for line, row in enumerate(rows, start=2):
                if None in row:  # more cells than header columns
                    row.pop(None)
                    counts["rejected"] += 1
                    say(f"REJECT  line {line}: more cells than header columns")
                    continue
                if not any((v or "").strip() for v in row.values()):
                    continue  # blank line: not a business, not a reject
                clean, reason = validate(row)
                label = f"{clean['name']} ({clean['suburb']})" if clean else ""
                if reason:
                    counts["rejected"] += 1
                    say(f"REJECT  line {line}: {reason}")
                    continue
                key = dedupe_key(clean["name"], clean["suburb"])
                if key in seen:
                    counts["skipped_duplicate"] += 1
                    say(f"SKIP    line {line}: {label} already exists (left unchanged)")
                    continue
                seen.add(key)
                session.add(Business(**clean, source=SOURCE, is_verified=False, is_active=True))
                counts["inserted"] += 1
                say(f"{'INSERT ' if apply else 'WOULD INSERT'} line {line}: {label}")
            if apply:
                session.commit()
            else:
                session.rollback()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
    finally:
        engine.dispose()

    mode = "APPLIED" if apply else "DRY RUN (nothing written; add --apply to write)"
    verb = "inserted" if apply else "would insert"
    say(f"{mode}: {verb} {counts['inserted']} / skipped duplicate "
        f"{counts['skipped_duplicate']} / rejected {counts['rejected']}")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import owner-verified businesses from a CSV. Dry run unless --apply.")
    parser.add_argument("--csv", required=True, type=pathlib.Path, help="CSV file to import")
    parser.add_argument("--db", required=True,
                        help="SQLAlchemy URL, e.g. sqlite:////tmp/looper-copy.db")
    parser.add_argument("--apply", action="store_true",
                        help="write the inserts (default: dry run, writes nothing)")
    args = parser.parse_args(argv)
    try:
        run(args.csv, args.db, args.apply)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

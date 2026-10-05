#!/usr/bin/env python3
"""Online-safe backup of the Looper SQLite database (looper#56).

Usage (from anywhere):
    LOOPER_DB_URL=sqlite:////app/data/looper.db \
        python backend/scripts/sqlite_backup.py --out-dir /backups [--keep 14]

What it does, in order:
  1. Opens the live database READ-ONLY (``file:...?mode=ro``) and copies it
     with SQLite's online backup API (``Connection.backup``), never a file
     copy, so a backup taken while the app writes is still consistent.
  2. Writes to a hidden ``.looper-<UTC>.db.partial`` file in ``--out-dir``,
     runs ``PRAGMA integrity_check`` on it, and only then renames it to
     ``looper-<UTC>.db``. A failed run leaves no half-written backup behind.
  3. Keeps the newest ``--keep`` backups. It only ever deletes files in
     ``--out-dir`` whose name matches its own ``looper-<UTC>.db`` pattern.
  4. Prints ONE summary line (file name, size, table/row counts, timing).
     No row data, so no PII. Exits non-zero on any failure.

Backups contain raw names and mobile numbers from ``users``: keep them on a
private volume, never in git. See docs/RUNBOOK-BACKUP-RESTORE.md.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

DEFAULT_DB_URL = "sqlite:///data/looper.db"  # same default as backend/models.py
DEFAULT_KEEP = 14
BACKUP_RE = re.compile(r"^looper-\d{8}T\d{6}Z\.db$")


class BackupError(Exception):
    """Any failure that must end the run with a non-zero exit."""


def db_path_from_url(db_url: str) -> pathlib.Path:
    """``sqlite:///rel/path.db`` or ``sqlite:////abs/path.db`` -> Path.

    Relative paths resolve against the current directory, like SQLAlchemy.
    """
    prefix = "sqlite:///"
    if not db_url.startswith(prefix):
        raise BackupError("LOOPER_DB_URL is not a sqlite:/// file URL")
    raw = db_url[len(prefix):].split("?", 1)[0]
    if not raw or raw == ":memory:":
        raise BackupError("LOOPER_DB_URL points at an in-memory database")
    return pathlib.Path(raw).resolve()


def backup_name(now: datetime) -> str:
    return f"looper-{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}.db"


def _open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    # mode=ro: SQLite refuses every write and never creates a missing file.
    return sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, timeout=30)


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def integrity_ok(path: pathlib.Path) -> bool:
    conn = _open_readonly(path)
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    finally:
        conn.close()
    return rows == [("ok",)]


def prune(out_dir: pathlib.Path, keep: int) -> list[str]:
    """Delete all but the newest ``keep`` backups this script created.

    Names embed a sortable UTC timestamp, so name order is age order.
    Anything not matching ``looper-<UTC>.db`` is never touched.
    """
    ours = sorted(p.name for p in out_dir.iterdir() if p.is_file() and BACKUP_RE.match(p.name))
    doomed = ours[:-keep] if keep > 0 else []
    for name in doomed:
        (out_dir / name).unlink()
    return doomed


def run_backup(db_url: str, out_dir: pathlib.Path, keep: int = DEFAULT_KEEP,
               now: datetime | None = None) -> dict:
    if keep < 1:
        raise BackupError("--keep must be at least 1")
    src = db_path_from_url(db_url)
    if not src.is_file():
        raise BackupError("source database file does not exist")
    out_dir = out_dir.resolve()
    if out_dir == src.parent:
        raise BackupError("--out-dir must not be the live database's own folder")
    out_dir.mkdir(parents=True, exist_ok=True)

    name = backup_name(now or datetime.now(timezone.utc))
    final = out_dir / name
    if final.exists():
        raise BackupError(f"{name} already exists; refusing to overwrite")
    partial = out_dir / f".{name}.partial"

    started = time.monotonic()
    try:
        source = _open_readonly(src)
        dest = sqlite3.connect(partial)
        try:
            # pages=-1 copies everything in one step under a read lock, so the
            # copy is a single consistent snapshot even while the app writes.
            source.backup(dest, pages=-1)
            counts = _table_counts(dest)
        finally:
            dest.close()
            source.close()
        if not integrity_ok(partial):
            raise BackupError("integrity_check failed on the copy")
        os.replace(partial, final)
    except sqlite3.Error as exc:
        raise BackupError(f"sqlite error: {exc}") from exc
    finally:
        if partial.exists():
            partial.unlink()

    removed = prune(out_dir, keep)
    return {
        "file": name,
        "bytes": final.stat().st_size,
        "tables": len(counts),
        "rows": sum(counts.values()),
        "counts": counts,
        "removed": removed,
        "kept": sum(1 for p in out_dir.iterdir() if BACKUP_RE.match(p.name)),
        "seconds": round(time.monotonic() - started, 3),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Online-safe backup of the Looper SQLite DB.")
    ap.add_argument("--out-dir", required=True, type=pathlib.Path,
                    help="folder for looper-<UTC>.db copies (a separate volume, not /app/data)")
    ap.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                    help=f"how many newest backups to keep (default {DEFAULT_KEEP})")
    args = ap.parse_args(argv)
    try:
        r = run_backup(os.getenv("LOOPER_DB_URL", DEFAULT_DB_URL), args.out_dir, args.keep)
    except (BackupError, OSError) as exc:
        print(f"backup FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"backup ok file={r['file']} bytes={r['bytes']} tables={r['tables']} "
          f"rows={r['rows']} integrity=ok kept={r['kept']} removed={len(r['removed'])} "
          f"seconds={r['seconds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

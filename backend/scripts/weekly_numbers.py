#!/usr/bin/env python3
"""Weekly numbers: a read-only report from the Looper DB (looper#68).

Usage (run it against a BACKUP copy, never the live file):
    python backend/scripts/weekly_numbers.py --db /backups/looper-<UTC>.db [--days 7] [--json]

What it reports, for the last ``--days`` days and the window before it
(same length, so there is a trend):
  - queries from ``training_log``: total, by ``intent``, distinct sessions
  - zero-result searches (search rows whose ``response_text`` ends in `` []``,
    see routes/search.py) as a count and a %
  - the top 10 zero-result query texts, lowercased and grouped, ONLY when a
    text occurs at least twice (no one-off free text), PII-scrubbed again
  - bridge events by ``status`` (dead-letter watch)
plus current totals: active businesses, businesses with a HybridCard, public
reviews, active map pins, active deals.

Safety: opens the DB with ``file:...?mode=ro``, so SQLite refuses every write
and never creates a missing file (exit 2). It never prints names, mobiles or
any column of ``users``. Stdlib only, plus ``scrub_pii`` from the backend.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from services.telemetry import scrub_pii  # noqa: E402  (importing models never opens a DB)

TOP_N = 10
MIN_REPEATS = 2  # a zero-result text must occur this often to be listed
# routes/discover.py logs a synthetic query; everything else is a search.
DISCOVER_PREFIX = "discover suburb="


def open_readonly(path: pathlib.Path) -> sqlite3.Connection:
    # mode=ro: every write fails and a missing file is NOT created.
    return sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, timeout=30)


def _ts(dt: datetime) -> str:
    # SQLAlchemy stores naive UTC as 'YYYY-MM-DD HH:MM:SS[.ffffff]';
    # queries wrap columns in datetime() so either separator compares right.
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _window(conn: sqlite3.Connection, tables: set[str], start: str, end: str) -> dict:
    out: dict = {"queries": 0, "by_intent": {}, "sessions": 0, "searches": 0,
                 "zero_result": 0, "zero_result_pct": None, "top_zero_result": [],
                 "bridge_by_status": {}}
    if "training_log" in tables:
        where = "datetime(created_at) >= ? AND datetime(created_at) < ?"
        rng = (start, end)
        out["queries"] = conn.execute(
            f"SELECT COUNT(*) FROM training_log WHERE {where}", rng).fetchone()[0]
        out["by_intent"] = {(k or "(none)"): n for k, n in conn.execute(
            f"SELECT intent, COUNT(*) FROM training_log WHERE {where} "
            "GROUP BY intent ORDER BY COUNT(*) DESC, intent", rng)}
        out["sessions"] = conn.execute(
            f"SELECT COUNT(DISTINCT session_id) FROM training_log WHERE {where}",
            rng).fetchone()[0]
        search = f"{where} AND query_text NOT LIKE '{DISCOVER_PREFIX}%'"
        out["searches"] = conn.execute(
            f"SELECT COUNT(*) FROM training_log WHERE {search}", rng).fetchone()[0]
        zero = f"{search} AND response_text LIKE '% []'"
        out["zero_result"] = conn.execute(
            f"SELECT COUNT(*) FROM training_log WHERE {zero}", rng).fetchone()[0]
        if out["searches"]:
            out["zero_result_pct"] = round(100 * out["zero_result"] / out["searches"], 1)
        out["top_zero_result"] = [
            {"query": scrub_pii(q), "count": n} for q, n in conn.execute(
                f"SELECT lower(trim(query_text)) AS q, COUNT(*) FROM training_log "
                f"WHERE {zero} GROUP BY q HAVING COUNT(*) >= ? "
                "ORDER BY COUNT(*) DESC, q LIMIT ?", (*rng, MIN_REPEATS, TOP_N))]
    if "bridge_events" in tables:
        out["bridge_by_status"] = {(k or "(none)"): n for k, n in conn.execute(
            "SELECT status, COUNT(*) FROM bridge_events "
            "WHERE datetime(received_at) >= ? AND datetime(received_at) < ? "
            "GROUP BY status ORDER BY status", (start, end))}
    return out


def _count(conn: sqlite3.Connection, tables: set[str], table: str, where: str,
           params: tuple = ()) -> int | None:
    if table not in tables:
        return None
    return conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {where}', params).fetchone()[0]


def _totals(conn: sqlite3.Connection, tables: set[str], now: str) -> dict:
    return {
        "active_businesses": _count(conn, tables, "businesses", "is_active = 1"),
        "businesses_with_card": _count(
            conn, tables, "businesses",
            "is_active = 1 AND hybrid_card_id IS NOT NULL AND hybrid_card_id != ''"),
        "public_reviews": _count(conn, tables, "reviews", "is_public = 1"),
        "active_map_pins": _count(
            conn, tables, "map_pins",
            "is_active = 1 AND (expires_at IS NULL OR datetime(expires_at) > ?)", (now,)),
        "active_deals": _count(conn, tables, "deals", "active = 1"),
    }


def build_report(db_path: pathlib.Path, days: int = 7, now: datetime | None = None) -> dict:
    """Read-only. Raises FileNotFoundError when ``db_path`` does not exist."""
    if not db_path.is_file():
        raise FileNotFoundError(str(db_path))
    now = now or datetime.now(timezone.utc)
    cur_start, prev_start = now - timedelta(days=days), now - timedelta(days=2 * days)
    conn = open_readonly(db_path)
    try:
        tables = _tables(conn)
        return {
            "generated_at": _ts(now) + "Z",
            "days": days,
            "current": _window(conn, tables, _ts(cur_start), _ts(now)),
            "previous": _window(conn, tables, _ts(prev_start), _ts(cur_start)),
            "totals": _totals(conn, tables, _ts(now)),
        }
    finally:
        conn.close()


def _trend(cur, prev, unit: str = "") -> str:
    if cur is None or prev is None:
        return ""
    delta = cur - prev
    if isinstance(delta, float):
        delta = round(delta, 1)
    return f" ({'+' if delta >= 0 else ''}{delta}{unit} vs prev)"


def _pairs(d: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in d.items()) or "none"


def format_text(r: dict) -> str:
    c, p, t = r["current"], r["previous"], r["totals"]
    pct = "n/a" if c["zero_result_pct"] is None else f"{c['zero_result_pct']}%"
    lines = [
        f"Looper weekly numbers: last {r['days']} days to {r['generated_at']}",
        f"Queries: {c['queries']}{_trend(c['queries'], p['queries'])}",
        f"  by intent: {_pairs(c['by_intent'])}",
        f"Sessions: {c['sessions']}{_trend(c['sessions'], p['sessions'])}",
        f"Zero-result searches: {c['zero_result']} of {c['searches']} ({pct})"
        f"{_trend(c['zero_result_pct'], p['zero_result_pct'], ' pts')}",
        f"Asked for, found nothing (seen {MIN_REPEATS}+ times):",
    ]
    lines += [f"  {z['count']}x {z['query']}" for z in c["top_zero_result"]] or ["  none"]
    lines += [
        f"Bridge events: {_pairs(c['bridge_by_status'])}",
        f"Now: {t['active_businesses']} active businesses "
        f"({t['businesses_with_card']} with a HybridCard), {t['public_reviews']} public reviews,",
        f"     {t['active_map_pins']} active map pins, {t['active_deals']} active deals",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only weekly numbers from a Looper SQLite DB.")
    ap.add_argument("--db", required=True, type=pathlib.Path,
                    help="path to a looper.db file (use a backup copy, not the live DB)")
    ap.add_argument("--days", type=int, default=7, help="window length in days (default 7)")
    ap.add_argument("--json", action="store_true", help="print one JSON object instead of text")
    args = ap.parse_args(argv)
    if args.days < 1:
        print("--days must be at least 1", file=sys.stderr)
        return 2
    try:
        report = build_report(args.db, args.days)
    except FileNotFoundError:
        print(f"no database file at {args.db} (nothing was created)", file=sys.stderr)
        return 2
    except sqlite3.Error as exc:
        print(f"could not read {args.db}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True) if args.json else format_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

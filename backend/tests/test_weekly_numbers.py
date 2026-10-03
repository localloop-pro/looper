"""looper#68 — backend/scripts/weekly_numbers.py: read-only weekly report.

Every test builds its own throwaway DB in tmp_path from the real models
schema with obviously fake rows. Nothing here runs seed.py or touches the
shared test DB from conftest.
"""
import json
import pathlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine

import models

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import weekly_numbers  # noqa: E402

NOW = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
ZERO = "I couldn't find any  businesses matching 'x' in this area yet. []"
HITS = "Here are 2 options for 'cafe'. [Fake Cafe A, Fake Cafe B]"


def _at(days_ago: float) -> str:
    # The format SQLAlchemy writes for DateTime columns on SQLite.
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S.%f")


def _make_db(path: pathlib.Path) -> pathlib.Path:
    engine = create_engine(f"sqlite:///{path}")
    models.Base.metadata.create_all(engine)
    engine.dispose()
    log = [  # (query_text, response_text, intent, session_id, days_ago)
        # current window: last 7 days
        ("Hairdresser", ZERO, "search", "s1", 1),
        ("hairdresser ", ZERO, "search", "s2", 2),
        ("  HAIRDRESSER", ZERO, "search", "s2", 3),
        ("plumber in bondi", ZERO, "search", "s3", 1),          # one-off: never listed
        ("email me at [email]", ZERO, "search", "s3", 2),       # scrubbed on write
        ("Email me at [email]", ZERO, "search", None, 2),
        ("call 0412 345 678", ZERO, "search", "s4", 4),         # pre-scrub legacy row
        ("call 0412 345 678", ZERO, "search", "s4", 5),
        ("cafe", HITS, "voice", "s1", 1),
        ("discover suburb=bondi category=", "3 options around Bondi", "discover", "s3", 1),
        # previous window: 7-14 days ago
        ("vet", ZERO, "search", "p1", 8),
        ("cafe", HITS, "search", "p2", 10),
        # outside both windows: must never count
        ("hairdresser", ZERO, "search", "old", 30),
        ("hairdresser", ZERO, "search", "old", 31),
    ]
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("INSERT INTO users (id, first_name, mobile_number, join_code) "
                     "VALUES (1, 'Test', '0400000001', 'J00001')")
        conn.executemany(
            "INSERT INTO training_log (query_text, response_text, intent, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)", [(q, r, i, s, _at(d)) for q, r, i, s, d in log])
        conn.executemany(
            "INSERT INTO bridge_events (event_id, event_type, status, received_at) VALUES (?, ?, ?, ?)",
            [("e1", "deal.upserted", "processed", _at(1)),
             ("e2", "card.upserted", "processed", _at(2)),
             ("e3", "deal.upserted", "dead_letter", _at(3)),
             ("e4", "deal.upserted", "processed", _at(9)),
             ("e5", "deal.upserted", "dead_letter", _at(40))])
        conn.executemany(
            "INSERT INTO businesses (id, name, category, hybrid_card_id, is_active) VALUES (?, ?, ?, ?, ?)",
            [(1, "Fake A", "café", "card-a", 1), (2, "Fake B", "café", "card-b", 1),
             (3, "Fake C", "vet", "", 1), (4, "Fake D", "vet", "card-d", 0)])
        conn.executemany(
            "INSERT INTO reviews (business_id, user_id, rating, is_public) VALUES (?, 1, 5, ?)",
            [(1, 1), (2, 1), (3, 0)])
        conn.executemany(
            "INSERT INTO map_pins (user_id, pin_type, title, lat, lng, expires_at, is_active) "
            "VALUES (1, 'offering', 'Fake pin', 0, 0, ?, ?)",
            [(None, 1), (_at(1), 1), (_at(-5), 1), (None, 0)])
        conn.executemany(
            "INSERT INTO deals (deal_id, business_id, active) VALUES (?, 1, ?)",
            [("d1", 1), ("d2", 0)])
    conn.close()
    return path


def test_every_number_threshold_and_trend(tmp_path):
    db = _make_db(tmp_path / "looper.db")
    r = weekly_numbers.build_report(db, days=7, now=NOW)
    cur, prev = r["current"], r["previous"]

    assert cur["queries"] == 10
    assert cur["by_intent"] == {"search": 8, "voice": 1, "discover": 1}
    assert cur["sessions"] == 4  # s1..s4; NULL session not counted
    assert cur["searches"] == 9  # discover's synthetic query is not a search
    assert cur["zero_result"] == 8
    assert cur["zero_result_pct"] == 88.9
    # >=2 threshold: the one-off "plumber in bondi" is never shown; grouping is
    # lowercase + trimmed; PII is scrubbed again on output.
    assert cur["top_zero_result"] == [
        {"query": "hairdresser", "count": 3},
        {"query": "call [mobile]", "count": 2},
        {"query": "email me at [email]", "count": 2},
    ]
    assert cur["bridge_by_status"] == {"dead_letter": 1, "processed": 2}

    assert prev["queries"] == 2
    assert prev["searches"] == 2 and prev["zero_result"] == 1
    assert prev["zero_result_pct"] == 50.0
    assert prev["top_zero_result"] == []  # "vet" occurs once
    assert prev["bridge_by_status"] == {"processed": 1}

    assert r["totals"] == {"active_businesses": 3, "businesses_with_card": 2,
                           "public_reviews": 2, "active_map_pins": 2, "active_deals": 1}

    text = weekly_numbers.format_text(r)
    assert "Queries: 10 (+8 vs prev)" in text
    assert "Zero-result searches: 8 of 9 (88.9%) (+38.9 pts vs prev)" in text
    assert "3x hairdresser" in text
    assert "plumber" not in text and "0412" not in text and "@" not in text
    assert len(text.splitlines()) <= 16


def test_db_bytes_unchanged_and_no_side_files(tmp_path):
    db = _make_db(tmp_path / "looper.db")
    before = db.read_bytes()
    files_before = sorted(p.name for p in tmp_path.iterdir())
    assert weekly_numbers.main(["--db", str(db)]) == 0
    assert weekly_numbers.main(["--db", str(db), "--json", "--days", "3"]) == 0
    assert db.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == files_before


def test_connection_is_read_only(tmp_path):
    db = _make_db(tmp_path / "looper.db")
    conn = weekly_numbers.open_readonly(db)
    try:
        try:
            conn.execute("DELETE FROM training_log")
        except sqlite3.OperationalError as exc:
            assert "readonly" in str(exc)
        else:
            raise AssertionError("write should be refused")
    finally:
        conn.close()


def test_missing_db_exits_nonzero_and_creates_nothing(tmp_path, capsys):
    missing = tmp_path / "nope" / "looper.db"
    assert weekly_numbers.main(["--db", str(missing)]) == 2
    assert not missing.exists() and not missing.parent.exists()
    missing2 = tmp_path / "looper.db"
    assert weekly_numbers.main(["--db", str(missing2)]) == 2
    assert not missing2.exists()
    assert "nothing was created" in capsys.readouterr().err


def test_cli_json_is_one_object(tmp_path):
    db = _make_db(tmp_path / "looper.db")
    out = subprocess.run([sys.executable, str(SCRIPTS / "weekly_numbers.py"), "--db", str(db),
                          "--json"], capture_output=True, text=True, check=True).stdout
    report = json.loads(out)
    assert set(report) == {"generated_at", "days", "current", "previous", "totals"}
    assert report["days"] == 7


def test_empty_schema_reports_zeros(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()  # a valid DB with no tables (old or fresh install)
    r = weekly_numbers.build_report(db, now=NOW)
    assert r["current"]["queries"] == 0 and r["current"]["zero_result_pct"] is None
    assert r["totals"]["active_businesses"] is None
    assert "Zero-result searches: 0 of 0 (n/a)" in weekly_numbers.format_text(r)


def test_unicode_repeat_grouping_in_both_windows(tmp_path):
    db = _make_db(tmp_path / "looper.db")
    with sqlite3.connect(db) as conn:
        conn.executemany(
            "INSERT INTO training_log (query_text, response_text, intent, created_at) "
            "VALUES (?, ?, 'search', ?)",
            [(q, ZERO, _at(d)) for q, d in
             [("CAFÉ", 1), (" café ", 2), ("CAFÉ", 8), ("café", 9)]])
    r = weekly_numbers.build_report(db, now=NOW)
    for window in ("current", "previous"):
        assert {"query": "café", "count": 2} in r[window]["top_zero_result"]


def test_api_to_report_classifies_private_intents(client, db, tmp_path):
    # Actual API writes, including single-occurrence PII and a name that a
    # contact-detail regex cannot recognize. Use only synthetic details.
    intents = ["qa-owner@example.invalid", "qa-other@example.invalid",
               "0412 345 678", "+61 412 345 679", "Synthetic Owner", "other"]
    for n, intent in enumerate(intents):
        response = client.get("/api/search", params={
            "q": "CAFÉ" if n == 0 else "café" if n == 1 else f"missing-{n}",
            "intent": intent})
        assert response.status_code == 200
        assert response.json()["results"] == []
    assert db.query(models.TrainingLog).count() == len(intents)
    # The reporter operates on a backup, exactly as the owner instructions say.
    backup = tmp_path / "api-backup.db"
    with sqlite3.connect(models.engine.url.database) as source:
        with sqlite3.connect(backup) as dest:
            source.backup(dest)
    before = backup.read_bytes()
    report = weekly_numbers.build_report(
        backup, now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert report["current"]["by_intent"] == {"other": len(intents)}
    assert report["current"]["queries"] == len(intents)
    assert report["current"]["top_zero_result"] == [{"query": "café", "count": 2}]
    for output in (json.dumps(report), weekly_numbers.format_text(report)):
        for intent in intents[:-1]:
            assert intent not in output
    assert backup.read_bytes() == before


def test_intent_collapse_preserves_counts_in_both_windows(tmp_path):
    db = _make_db(tmp_path / "looper.db")
    with sqlite3.connect(db) as conn:
        conn.executemany(
            "INSERT INTO training_log (query_text, response_text, intent, created_at) "
            "VALUES ('one-off', ?, ?, ?)",
            [(ZERO, intent, _at(d)) for d in (1, 8)
             for intent in (None, "", "qa@example.invalid", "0412345678", "other")])
    report = weekly_numbers.build_report(db, now=NOW)
    for window in ("current", "previous"):
        intents = report[window]["by_intent"]
        assert intents["(none)"] == 2
        assert intents["other"] == 3
        assert sum(intents.values()) == report[window]["queries"]


def test_cli_needs_only_stdlib(tmp_path):
    script = str(SCRIPTS / "weekly_numbers.py")
    help_run = subprocess.run([sys.executable, "-S", script, "--help"],
                              capture_output=True, text=True, check=True)
    assert "Read-only weekly numbers" in help_run.stdout
    db = _make_db(tmp_path / "looper.db")
    before = db.read_bytes()
    for mode in ([], ["--json"]):
        result = subprocess.run([sys.executable, "-S", script, "--db", str(db), *mode],
                                capture_output=True, text=True, check=True)
        assert "queries" in result.stdout.lower()
    assert db.read_bytes() == before

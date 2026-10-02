"""looper#56 — backend/scripts/sqlite_backup.py: online backup + restore drill.

Every test builds its own throwaway DB in tmp_path from the real models
schema with obviously fake rows. Nothing here runs seed.py or touches the
shared test DB from conftest.
"""
import pathlib
import shutil
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

import models

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import sqlite_backup  # noqa: E402

T0 = datetime(2026, 10, 2, 3, 0, 0, tzinfo=timezone.utc)


def _make_db(path: pathlib.Path, users=5, businesses=7) -> str:
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(path)
    with conn:
        for i in range(users):
            conn.execute("INSERT INTO users (first_name, mobile_number, join_code) VALUES (?, ?, ?)",
                         (f"Test{i}", f"0400000{i:03d}", f"J{i:05d}"))
        for i in range(businesses):
            conn.execute("INSERT INTO businesses (name, category) VALUES (?, ?)",
                         (f"Fake Biz {i}", "café"))
    conn.close()
    return url


def _counts(path: pathlib.Path) -> dict:
    conn = sqlite3.connect(path)
    try:
        return sqlite_backup._table_counts(conn)
    finally:
        conn.close()


def test_backup_then_restore_matches_row_counts(tmp_path):
    live = tmp_path / "live" / "looper.db"
    live.parent.mkdir()
    url = _make_db(live)
    before = _counts(live)
    live_bytes = live.read_bytes()

    r = sqlite_backup.run_backup(url, tmp_path / "backups", now=T0)
    backup = tmp_path / "backups" / r["file"]
    assert r["file"] == "looper-20261002T030000Z.db"
    assert backup.is_file()
    assert r["counts"] == before and r["rows"] == sum(before.values())
    assert live.read_bytes() == live_bytes  # source untouched

    # Restore drill: the app's file is lost, swap the backup in, recount.
    restored = tmp_path / "restored" / "looper.db"
    restored.parent.mkdir()
    shutil.copy2(backup, restored)
    assert sqlite_backup.integrity_ok(restored)
    assert _counts(restored) == before
    assert before["users"] == 5 and before["businesses"] == 7

    # The ORM can read the restored file like the app would.
    engine = create_engine(f"sqlite:///{restored}")
    with engine.connect() as c:
        assert c.exec_driver_sql("SELECT COUNT(*) FROM businesses").scalar() == 7
    engine.dispose()
    # No partial file left behind.
    assert [p.name for p in (tmp_path / "backups").iterdir()] == [r["file"]]


def test_retention_removes_oldest_and_only_its_own_files(tmp_path):
    live = tmp_path / "live" / "looper.db"
    live.parent.mkdir()
    url = _make_db(live)
    out = tmp_path / "backups"
    out.mkdir()
    # Files the script did not create must survive, even look-alikes.
    strangers = ["notes.txt", "looper.db", "looper-latest.db", "looper-20200101T000000Z.db.bak"]
    for s in strangers:
        (out / s).write_text("keep me")

    names = [sqlite_backup.run_backup(url, out, keep=3, now=T0 + timedelta(days=d))["file"]
             for d in range(4)]
    kept = sorted(p.name for p in out.iterdir() if sqlite_backup.BACKUP_RE.match(p.name))
    assert kept == names[1:]  # oldest gone, newest three kept
    assert not (out / names[0]).exists()
    for s in strangers:
        assert (out / s).read_text() == "keep me"


def test_backup_during_concurrent_writes_passes_integrity(tmp_path):
    live = tmp_path / "live" / "looper.db"
    live.parent.mkdir()
    url = _make_db(live, users=0, businesses=0)
    stop = threading.Event()
    written = []
    errors = []

    def writer():
        conn = sqlite3.connect(live, timeout=30)
        try:
            i = 0
            while not stop.is_set() or i < 200:
                with conn:
                    conn.execute("INSERT INTO businesses (name, category, description) VALUES (?, ?, ?)",
                                 (f"Load {i}", "test", "x" * 2000))
                written.append(i)
                i += 1
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            conn.close()

    t = threading.Thread(target=writer)
    t.start()
    deadline = time.monotonic() + 30
    while len(written) < 50 and not errors and time.monotonic() < deadline:
        time.sleep(0.005)  # make sure writes are really in flight
    assert len(written) >= 50, errors
    try:
        results = [sqlite_backup.run_backup(url, tmp_path / "backups", keep=10,
                                            now=T0 + timedelta(seconds=s)) for s in range(3)]
    finally:
        stop.set()
        t.join()

    assert not errors
    for r in results:
        path = tmp_path / "backups" / r["file"]
        assert sqlite_backup.integrity_ok(path)
        assert 50 <= r["counts"]["businesses"] <= len(written)


def test_source_is_opened_read_only(tmp_path, monkeypatch):
    live = tmp_path / "live" / "looper.db"
    live.parent.mkdir()
    _make_db(live)
    conn = sqlite_backup._open_readonly(live)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM users")
    conn.close()
    assert _counts(live)["users"] == 5


def test_cli_prints_one_pii_free_line(tmp_path, monkeypatch, capsys):
    live = tmp_path / "live" / "looper.db"
    live.parent.mkdir()
    monkeypatch.setenv("LOOPER_DB_URL", _make_db(live))
    assert sqlite_backup.main(["--out-dir", str(tmp_path / "b"), "--keep", "2"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 1 and out.startswith("backup ok file=looper-")
    assert "integrity=ok" in out and "rows=12" in out
    for pii in ("Test0", "0400000", "J00000"):
        assert pii not in out


@pytest.mark.parametrize("setup, msg", [
    ("missing", "does not exist"),
    ("same_dir", "own folder"),
    ("memory", "in-memory"),
])
def test_failures_exit_nonzero(tmp_path, monkeypatch, capsys, setup, msg):
    live = tmp_path / "looper.db"
    out_dir = tmp_path / "backups"
    if setup == "missing":
        url = f"sqlite:///{live}"
    elif setup == "same_dir":
        url = _make_db(live)
        out_dir = tmp_path
    else:
        url = "sqlite:///:memory:"
    monkeypatch.setenv("LOOPER_DB_URL", url)
    assert sqlite_backup.main(["--out-dir", str(out_dir)]) == 1
    assert msg in capsys.readouterr().err
    assert not (live.exists() and setup == "missing")  # never creates the source


def test_corrupt_copy_is_rejected_and_not_kept(tmp_path, monkeypatch):
    live = tmp_path / "live" / "looper.db"
    live.parent.mkdir()
    url = _make_db(live)
    monkeypatch.setattr(sqlite_backup, "integrity_ok", lambda _p: False)
    with pytest.raises(sqlite_backup.BackupError, match="integrity"):
        sqlite_backup.run_backup(url, tmp_path / "backups", now=T0)
    assert list((tmp_path / "backups").iterdir()) == []

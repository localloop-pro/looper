"""looper#74 — backend/scripts/import_businesses.py: owner-verified CSV import.

Every DB here is a throwaway SQLite file in tmp_path (or conftest's test DB
for the /api/search check). All business names are obviously fake test
fixtures and live only in this file, never in the repo's data or templates.
"""
import csv
import hashlib
import io
import pathlib
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from models import Business, Review, User

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import import_businesses  # noqa: E402

HEADER = import_businesses.COLUMNS
REPO = pathlib.Path(__file__).resolve().parents[2]


def _row(**kw) -> dict:
    base = {"name": "Test Fake Bakery", "category": "bakery", "suburb": "Bondi",
            "address": "1 Test St", "lat": "-33.89", "lng": "151.27", "phone": "",
            "website": "", "description": "test fixture"}
    base.update(kw)
    return base


def _csv(path: pathlib.Path, rows: list[dict], header=HEADER) -> pathlib.Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return path


def _db(tmp_path: pathlib.Path) -> tuple[str, pathlib.Path]:
    path = tmp_path / "looper-copy.db"
    engine = create_engine(f"sqlite:///{path}")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Business(name="Café Test Card", category="café", suburb="Bondi",
                         lat=-33.89, lng=151.27, source="hybrid_card",
                         hybrid_card_id="card-test-1", description="from the bridge",
                         website="https://test-card.hybridcard.ai"))
    session.commit()
    session.close()
    engine.dispose()
    return f"sqlite:///{path}", path


def _rows(url: str) -> list[Business]:
    engine = create_engine(url)
    session = sessionmaker(bind=engine)()
    out = session.query(Business).order_by(Business.id).all()
    session.expunge_all()
    session.close()
    engine.dispose()
    return out


def _run(csv_path, url, apply=False):
    out = io.StringIO()
    counts = import_businesses.run(csv_path, url, apply, out=out)
    return counts, out.getvalue()


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_dry_run_writes_nothing(tmp_path):
    url, path = _db(tmp_path)
    before = _sha(path)
    src = _csv(tmp_path / "in.csv", [_row(), _row(name="Test Fake Plumber", category="plumber")])
    counts, out = _run(src, url)
    assert counts == {"inserted": 2, "skipped_duplicate": 0, "rejected": 0}
    assert "WOULD INSERT" in out and "DRY RUN" in out
    assert "would insert 2 / skipped duplicate 0 / rejected 0" in out
    assert _sha(path) == before
    assert len(_rows(url)) == 1


def test_apply_inserts_valid_rows_with_owner_verified_fields(tmp_path):
    url, _ = _db(tmp_path)
    src = _csv(tmp_path / "in.csv", [_row(website="https://fake-bakery.example",
                                          phone="02 0000 0000")])
    counts, out = _run(src, url, apply=True)
    assert counts["inserted"] == 1
    assert "APPLIED: inserted 1 / skipped duplicate 0 / rejected 0" in out
    new = _rows(url)[-1]
    assert new.name == "Test Fake Bakery" and new.suburb == "Bondi"
    assert (new.lat, new.lng) == (-33.89, 151.27)
    assert new.website == "https://fake-bakery.example"
    assert new.source == "owner_verified"
    assert new.is_verified is False and new.is_active is True
    assert new.hybrid_card_id is None


def test_duplicate_of_hybrid_card_row_is_skipped_and_unchanged(tmp_path):
    url, _ = _db(tmp_path)
    before = _rows(url)[0]
    snapshot = {c.name: getattr(before, c.name) for c in Business.__table__.columns}
    # Accent, case and spacing differ; the folded (name, suburb) is the same.
    src = _csv(tmp_path / "in.csv", [_row(name="  CAFE  test card ", suburb="bondi",
                                          category="other", description="overwrite?")])
    counts, out = _run(src, url, apply=True)
    assert counts == {"inserted": 0, "skipped_duplicate": 1, "rejected": 0}
    assert "already exists (left unchanged)" in out
    rows = _rows(url)
    assert len(rows) == 1
    assert {c.name: getattr(rows[0], c.name) for c in Business.__table__.columns} == snapshot


def test_bad_rows_are_rejected_with_reasons_and_the_rest_carry_on(tmp_path):
    url, _ = _db(tmp_path)
    src = _csv(tmp_path / "in.csv", [
        _row(name=""),                                    # line 2
        _row(name="Test Bad Lat", lat="nan"),             # line 3
        _row(name="Test Inf Lng", lng="inf"),             # line 4
        _row(name="Test Swapped", lat="151.27", lng="-33.89"),  # line 5
        _row(name="Test London", lat="51.5", lng="-0.12"),      # line 6
        _row(name="Test Text Lat", lat="north"),          # line 7
        _row(name="Test Http", website="http://fake.example"),  # line 8
        _row(name="Test Good Row"),                       # line 9
        _row(name="Test No Category", category=""),       # line 10
    ])
    counts, out = _run(src, url, apply=True)
    assert counts == {"inserted": 1, "skipped_duplicate": 0, "rejected": 8}
    assert "line 2: missing name" in out
    assert "line 3: lat must be a finite number" in out
    assert "line 4: lng must be a finite number" in out
    assert "line 5: lat 151.27 is outside Australia" in out
    assert "line 6: lat 51.5 is outside Australia" in out
    assert "line 7: lat is not a number" in out
    assert "line 8: website must start with https://" in out
    assert "line 10: missing category" in out
    assert [b.name for b in _rows(url)] == ["Café Test Card", "Test Good Row"]


MALFORMED_WEBSITES = [
    "https://[bad",          # urlparse raises ValueError: Invalid IPv6 URL
    "https://[not-an-ip]/",  # same, with a closing bracket
    "https://:443",          # netloc but no hostname
    "https://user@:443",     # userinfo, still no hostname
    "https://",              # nothing after the scheme
]


def _malformed_website_csv(tmp_path):
    rows = [_row(name="Test Valid Before")]
    rows += [_row(name=f"Test Bad Site {i}", website=w) for i, w in enumerate(MALFORMED_WEBSITES)]
    rows.append(_row(name="Test Valid After"))
    return _csv(tmp_path / "in.csv", rows)


def test_malformed_website_is_rejected_and_dry_run_continues(tmp_path):
    url, path = _db(tmp_path)
    before = _sha(path)
    counts, out = _run(_malformed_website_csv(tmp_path), url)
    bad = len(MALFORMED_WEBSITES)
    assert counts == {"inserted": 2, "skipped_duplicate": 0, "rejected": bad}
    for line in range(3, 3 + bad):
        assert f"line {line}: website must start with https://" in out
    assert f"would insert 2 / skipped duplicate 0 / rejected {bad}" in out
    assert _sha(path) == before


def test_malformed_website_is_rejected_and_apply_continues(tmp_path):
    url, _ = _db(tmp_path)
    counts, out = _run(_malformed_website_csv(tmp_path), url, apply=True)
    bad = len(MALFORMED_WEBSITES)
    assert counts == {"inserted": 2, "skipped_duplicate": 0, "rejected": bad}
    assert f"APPLIED: inserted 2 / skipped duplicate 0 / rejected {bad}" in out
    assert [b.name for b in _rows(url)] == ["Café Test Card", "Test Valid Before", "Test Valid After"]


def test_cli_malformed_website_exits_zero_with_summary(tmp_path):
    url, _ = _db(tmp_path)
    src = _malformed_website_csv(tmp_path)
    proc = subprocess.run([sys.executable, str(SCRIPTS / "import_businesses.py"),
                           "--csv", str(src), "--db", url],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr
    assert f"would insert 2 / skipped duplicate 0 / rejected {len(MALFORMED_WEBSITES)}" in proc.stdout


def test_running_twice_inserts_nothing_new(tmp_path):
    url, _ = _db(tmp_path)
    src = _csv(tmp_path / "in.csv", [_row(), _row(name="Test Fake Florist", category="florist")])
    assert _run(src, url, apply=True)[0]["inserted"] == 2
    counts, _ = _run(src, url, apply=True)
    assert counts == {"inserted": 0, "skipped_duplicate": 2, "rejected": 0}
    assert len(_rows(url)) == 3


def test_duplicates_inside_one_csv_insert_once(tmp_path):
    url, _ = _db(tmp_path)
    src = _csv(tmp_path / "in.csv", [_row(), _row(name="test fake bakery", address="other")])
    counts, _ = _run(src, url, apply=True)
    assert counts == {"inserted": 1, "skipped_duplicate": 1, "rejected": 0}


def test_inactive_existing_row_is_not_reactivated_or_duplicated(tmp_path):
    url, _ = _db(tmp_path)
    engine = create_engine(url)
    session = sessionmaker(bind=engine)()
    session.query(Business).update({"is_active": False})
    session.commit()
    session.close()
    engine.dispose()
    src = _csv(tmp_path / "in.csv", [_row(name="Café Test Card")])
    assert _run(src, url, apply=True)[0]["skipped_duplicate"] == 1
    rows = _rows(url)
    assert len(rows) == 1 and rows[0].is_active is False


def test_missing_db_file_is_never_created(tmp_path):
    src = _csv(tmp_path / "in.csv", [_row()])
    missing = tmp_path / "nope.db"
    rc = import_businesses.main(["--csv", str(src), "--db", f"sqlite:///{missing}", "--apply"])
    assert rc == 2
    assert not missing.exists()


def test_db_without_businesses_table_is_refused(tmp_path):
    empty = tmp_path / "empty.db"
    create_engine(f"sqlite:///{empty}").connect().close()
    src = _csv(tmp_path / "in.csv", [_row()])
    assert import_businesses.main(["--csv", str(src), "--db", f"sqlite:///{empty}"]) == 2


def test_wrong_header_is_refused(tmp_path):
    url, _ = _db(tmp_path)
    src = _csv(tmp_path / "in.csv", [{"name": "x", "town": "y"}], header=["name", "town"])
    assert import_businesses.main(["--csv", str(src), "--db", url, "--apply"]) == 2
    assert len(_rows(url)) == 1


def test_cli_dry_run_by_default(tmp_path):
    url, path = _db(tmp_path)
    before = _sha(path)
    src = _csv(tmp_path / "in.csv", [_row()])
    proc = subprocess.run([sys.executable, str(SCRIPTS / "import_businesses.py"),
                           "--csv", str(src), "--db", url],
                          capture_output=True, text=True, check=True)
    assert "DRY RUN" in proc.stdout
    assert _sha(path) == before


def test_template_is_header_only():
    template = REPO / "docs" / "templates" / "businesses.csv"
    lines = template.read_text(encoding="utf-8").splitlines()
    assert lines == [",".join(HEADER)]


def test_imported_rows_rank_by_the_same_sort_keys_in_search(client, db):
    """Imported rows appear in /api/search and source never moves them.

    conftest's DB is a throwaway test file, so the importer can target it.
    """
    reviewer = User(first_name="Test", mobile_number="0400000074", join_code="T00074")
    card = Business(name="Test Card Plumber", category="plumber", suburb="Bondi",
                    lat=-33.893, lng=151.272, source="hybrid_card", hybrid_card_id="card-t")
    db.add_all([reviewer, card])
    db.commit()
    src = _csv(pathlib.Path(models.engine.url.database).with_name("test_import_74.csv"), [
        _row(name="Test Owner Plumber A", category="plumber", lat="-33.891", lng="151.271"),
        _row(name="Test Owner Plumber B", category="plumber", lat="-33.95", lng="151.25"),
    ])
    try:
        counts, _ = _run(src, str(models.engine.url), apply=True)
    finally:
        src.unlink()
    assert counts["inserted"] == 2
    b = db.query(Business).filter_by(name="Test Owner Plumber B").one()
    db.add(Review(business_id=b.id, user_id=reviewer.id, rating=4, is_public=True))
    db.commit()

    def order():
        r = client.get("/api/search", params={"q": "plumber", "lat": -33.89, "lng": 151.27,
                                              "radius_km": 20})
        assert r.status_code == 200
        return [x["name"] for x in r.json()["results"]]

    # relevance ties (category match) -> more reviews first -> nearer first.
    # (Coordinates avoid distance 0.0: search treats it as "unknown", 999.)
    expected = ["Test Owner Plumber B", "Test Owner Plumber A", "Test Card Plumber"]
    assert order() == expected
    # Flip every source: the order must not move (anti-bias).
    db.query(Business).update({"source": "manual"})
    db.commit()
    assert order() == expected
    db.query(Business).update({"source": "hybrid_card"})
    db.commit()
    assert order() == expected

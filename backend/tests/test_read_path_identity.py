"""Issue #30: the read-path speed-up must not change a single answer.

`fixtures/read_path_snapshot.json` was recorded with the ORIGINAL per-business
review queries (N+1) before the batching fix, on the bench's fake dataset
(400 businesses, 2,000 reviews, fixed seed). Every case must still return
the same ordered ids AND the same fields (counts, ratings, distances, top
review, card_url, totals, message).

Re-record ONLY for an intentional behaviour change:
    LOOPER_UPDATE_SNAPSHOT=1 .venv/bin/python -m pytest tests/test_read_path_identity.py
"""
import json
import os
import pathlib
import sys

from models import Deal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from bench_search import ENDPOINTS, build_dataset  # noqa: E402

SNAPSHOT = pathlib.Path(__file__).parent / "fixtures" / "read_path_snapshot.json"


def _collect(client):
    out = {}
    for path, cases in ENDPOINTS:
        for params in cases:
            key = f"{path}?{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
            resp = client.get(path, params=params)
            assert resp.status_code == 200, (key, resp.text)
            out[key] = resp.json()
    return out


def test_read_paths_match_pre_fix_snapshot(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "0")
    build_dataset(db, n_businesses=400, n_reviews=2000)
    got = _collect(client)
    if os.getenv("LOOPER_UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(got, indent=1, ensure_ascii=False, sort_keys=True))
    expected = json.loads(SNAPSHOT.read_text())
    assert set(got) == set(expected)
    for key in expected:
        exp_ids = [r.get("business_id", r.get("id")) for r in expected[key]["results"]]
        got_ids = [r.get("business_id", r.get("id")) for r in got[key]["results"]]
        assert got_ids == exp_ids, f"order changed for {key}"
        assert got[key] == expected[key], f"payload changed for {key}"
    # the fixture must exercise multi-result answers, not a trivial empty set
    assert sum(len(v["results"]) >= 3 for v in expected.values()) >= 8


def test_discount_and_card_never_change_order(client, db, monkeypatch):
    """Anti-bias proof on the batched path: maxing out every deal's discount
    and flipping card links on/off leaves every ordered list untouched."""
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "0")
    build_dataset(db, n_businesses=400, n_reviews=2000)
    before = _collect(client)
    for deal in db.query(Deal).all():
        deal.discount_size = 99
        deal.active = not deal.active
    db.commit()
    after = _collect(client)
    for key in before:
        ids_b = [r.get("business_id", r.get("id")) for r in before[key]["results"]]
        ids_a = [r.get("business_id", r.get("id")) for r in after[key]["results"]]
        assert ids_a == ids_b, f"discount/card changed order for {key}"


def test_fold_accents_ascii_fast_path_is_equivalent():
    """The ASCII shortcut must give exactly what the NFD walk gives."""
    import string
    import unicodedata

    from models import fold_accents

    def slow(value):
        return "".join(c for c in unicodedata.normalize("NFD", value)
                       if not unicodedata.combining(c)).lower()

    samples = [string.printable, "Bondi Beach", "SURRY HILLS", "", "Café", "CAFÉ crème",
               "Ñandú", "naïve", "Øresund", "ﬁg tree", "İstanbul", "ß"]
    for s in samples:
        assert fold_accents(s) == slow(s), s
    assert fold_accents(None) is None

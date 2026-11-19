"""#151: a known-suburb /api/discover must not return a business with no
coordinates from another suburb.

A business with NULL lat/lng cannot be radius-checked, so for a known suburb
(e.g. Bondi) it is only eligible when its own suburb field matches the
requested suburb (accent-folded). "North Bondi" and "Bondi Junction" are
their own suburbs, not Bondi. Radius rules and ranking are unchanged.
"""
import sys
import types
from contextlib import contextmanager

from models import Business


def _biz(db, **kw):
    defaults = dict(name="Bondi Cuts", category="hairdresser", suburb="Bondi",
                    lat=-33.8915, lng=151.2743, is_active=True)
    defaults.update(kw)
    b = Business(**defaults)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def _names(body):
    return sorted(r["name"] for r in body["results"])


def _seed(db):
    _biz(db)  # in Bondi, with coordinates
    _biz(db, name="Byron Trim", suburb="Byron Bay", lat=None, lng=None)
    _biz(db, name="Surry Hills Barber", suburb="Surry Hills", lat=None, lng=None)
    _biz(db, name="North Bondi Hair", suburb="North Bondi", lat=None, lng=None)
    _biz(db, name="Junction Blowdry", suburb="Bondi Junction", lat=None, lng=None)
    _biz(db, name="Bondí Hair Studio", suburb="Bondí", lat=None, lng=None)


class TestFallbackEngine:
    def test_no_coordinate_business_from_other_suburb_is_excluded(self, client, db):
        _seed(db)
        body = client.get("/api/discover", params={"suburb": "Bondi"}).json()
        assert body["engine"] == "fallback"
        assert "Byron Trim" not in _names(body)
        assert "Surry Hills Barber" not in _names(body)
        assert body["total_results"] == 2

    def test_overlapping_suburb_names_are_not_a_match(self, client, db):
        _seed(db)
        body = client.get("/api/discover", params={"suburb": "Bondi"}).json()
        assert "North Bondi Hair" not in _names(body)
        assert "Junction Blowdry" not in _names(body)

    def test_longer_suburb_keeps_its_own_business(self, client, db):
        _seed(db)
        body = client.get("/api/discover",
                          params={"suburb": "Bondi Junction", "radius_km": 0.5}).json()
        assert body["suburb"] == "bondi junction"
        assert _names(body) == ["Junction Blowdry"]

    def test_no_coordinate_business_in_requested_suburb_is_kept(self, client, db):
        _seed(db)
        body = client.get("/api/discover", params={"suburb": "Bondi"}).json()
        assert _names(body) == ["Bondi Cuts", "Bondí Hair Studio"]

    def test_coordinate_only_search_is_unchanged(self, client, db):
        # No suburb asked for, so there is nothing to match a no-coordinate
        # business against: it stays in, without a distance, as before.
        _seed(db)
        body = client.get("/api/discover",
                          params={"lat": -33.8915, "lng": 151.2743}).json()
        assert _names(body) == ["Bondi Cuts", "Bondí Hair Studio",
                                "Byron Trim", "Junction Blowdry",
                                "North Bondi Hair", "Surry Hills Barber"]


def _fake_typedb_module():
    """Minimal stand-in for `typedb.driver` whose graph holds no carded
    businesses, so `_graph_discover` runs on SQLite rows only."""
    tx = types.SimpleNamespace(query=types.SimpleNamespace(get=lambda _q: []))

    @contextmanager
    def _ctx(value):
        yield value

    session = types.SimpleNamespace(transaction=lambda *_a: _ctx(tx))
    driver = types.SimpleNamespace(session=lambda *_a: _ctx(session))
    mod = types.ModuleType("typedb.driver")
    mod.TypeDB = types.SimpleNamespace(core_driver=lambda _addr: _ctx(driver))
    mod.SessionType = types.SimpleNamespace(DATA="data")
    mod.TransactionType = types.SimpleNamespace(READ="read")
    return mod


class TestGraphEngine:
    def test_no_coordinate_business_from_other_suburb_is_excluded(
        self, client, db, monkeypatch
    ):
        monkeypatch.setenv("TYPEDB_ENABLED", "true")
        monkeypatch.setitem(sys.modules, "typedb", types.ModuleType("typedb"))
        monkeypatch.setitem(sys.modules, "typedb.driver", _fake_typedb_module())
        _seed(db)
        body = client.get("/api/discover", params={"suburb": "Bondi"}).json()
        assert body["engine"] == "graph"
        # Byron Bay, Surry Hills, North Bondi and Bondi Junction all dropped
        assert _names(body) == ["Bondi Cuts", "Bondí Hair Studio"]
        assert body["total_results"] == 2

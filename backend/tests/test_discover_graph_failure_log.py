"""Issue #152: a TypeDB graph failure in /api/discover must leave one warning
on the `looper.discover` logger (exception class + message, no caller location)
while the transparent SQLite fallback and response shape stay unchanged."""
import logging

from models import Business
from routes import discover as discover_route


class _GraphDown(RuntimeError):
    pass


def _boom(*args, **kwargs):
    raise _GraphDown("typedb connection refused")


def test_graph_failure_logs_one_warning_and_falls_back(client, db, caplog, monkeypatch):
    db.add(Business(name="Gertrude & Alice", category="café", suburb="Bondi Beach",
                    lat=-33.8893, lng=151.2735, is_active=True))
    db.commit()
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    monkeypatch.setattr(discover_route, "_graph_discover", _boom)
    caplog.set_level(logging.WARNING, logger="looper.discover")

    resp = client.get("/api/discover", params={
        "suburb": "Bondi", "lat": -33.8915, "lng": 151.2743, "category": "café"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["engine"] == "fallback"
    assert list(body) == ["engine", "suburb", "category", "radius_km",
                          "results", "total_results", "message"]
    assert [r["name"] for r in body["results"]] == ["Gertrude & Alice"]

    warnings = [r for r in caplog.records
                if r.name == "looper.discover" and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    text = warnings[0].getMessage()
    assert "_GraphDown" in text
    assert "typedb connection refused" in text
    # Never the caller's location (suburb, coordinates).
    for leaked in ("Bondi", "-33.8915", "151.2743"):
        assert leaked not in text
    assert warnings[0].exc_info is None  # no traceback (could carry locals/paths)


def test_graph_disabled_logs_nothing(client, db, caplog):
    caplog.set_level(logging.WARNING, logger="looper.discover")
    resp = client.get("/api/discover", params={"suburb": "Bondi"})
    assert resp.status_code == 200
    assert resp.json()["engine"] == "fallback"
    assert not [r for r in caplog.records if r.name == "looper.discover"]


def test_graph_failure_log_masks_typedb_address(client, db, caplog, monkeypatch):
    address = "typedb-internal.example:1729"
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    monkeypatch.setenv("TYPEDB_ADDRESS", address)

    def _refused(*args, **kwargs):
        raise ConnectionError(f"Unable to connect to TypeDB server at {address}")

    monkeypatch.setattr(discover_route, "_graph_discover", _refused)
    caplog.set_level(logging.WARNING, logger="looper.discover")

    assert client.get("/api/discover", params={"suburb": "Bondi"}).json()["engine"] == "fallback"
    [record] = [r for r in caplog.records if r.name == "looper.discover"]
    text = record.getMessage()
    assert "ConnectionError" in text and address not in text
    assert "[typedb-address]" in text

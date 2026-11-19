"""Issue #152: a TypeDB graph failure in /api/discover must leave one warning
on the `looper.discover` logger (exception class + scrubbed message) while the
transparent SQLite fallback and response shape stay unchanged. The warning
must never carry request values, coordinates, addresses or secrets."""
import logging

import pytest
from sqlalchemy.exc import OperationalError

from models import Business
from routes import discover as discover_route

REQUEST = {"suburb": "Bondi", "lat": -33.8915, "lng": 151.2743,
           "category": "private-query"}
TYPEDB_ADDRESS = "typedb-internal.example:1729"

# Anything request-derived or secret-like that must never reach the log.
FORBIDDEN = ("Bondi", "bondi", "-33.8915", "33.89", "151.2743", "151.27",
             "private-query", "private", "typedb-internal", "1729", "10.0.0.5",
             "hunter2", "admin", "secret", "password", "example", "SELECT")


class _GraphDown(RuntimeError):
    pass


class TypeDBDriverException(Exception):
    """Stand-in for the TypeDB driver's exception (module is what matters)."""


TypeDBDriverException.__module__ = "typedb.common.exception"


def _raiser(exc):
    def _raise(*args, **kwargs):
        raise exc
    return _raise


def _warnings(caplog):
    return [r for r in caplog.records
            if r.name == "looper.discover" and r.levelno == logging.WARNING]


def _fail_discover(client, caplog, monkeypatch, exc):
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    monkeypatch.setenv("TYPEDB_ADDRESS", TYPEDB_ADDRESS)
    monkeypatch.setattr(discover_route, "_graph_discover", _raiser(exc))
    caplog.set_level(logging.WARNING, logger="looper.discover")
    resp = client.get("/api/discover", params=REQUEST)
    assert resp.status_code == 200
    assert resp.json()["engine"] == "fallback"
    [record] = _warnings(caplog)
    assert record.exc_info is None  # no traceback (could carry locals/paths)
    return record.getMessage()


def test_graph_failure_logs_one_warning_and_falls_back(client, db, caplog, monkeypatch):
    db.add(Business(name="Gertrude & Alice", category="private-query", suburb="Bondi Beach",
                    lat=-33.8893, lng=151.2735, is_active=True))
    db.commit()
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    monkeypatch.setattr(discover_route, "_graph_discover",
                        _raiser(_GraphDown("typedb connection refused")))
    caplog.set_level(logging.WARNING, logger="looper.discover")

    resp = client.get("/api/discover", params=REQUEST)

    assert resp.status_code == 200
    body = resp.json()
    assert body["engine"] == "fallback"
    assert list(body) == ["engine", "suburb", "category", "radius_km",
                          "results", "total_results", "message"]
    assert [r["name"] for r in body["results"]] == ["Gertrude & Alice"]

    [record] = _warnings(caplog)
    text = record.getMessage()
    assert text.startswith("discover graph engine failed, using fallback: ")
    assert text.endswith("_GraphDown: typedb connection refused")


@pytest.mark.parametrize("exc", [
    RuntimeError("category=private-query lat=-33.8915 password=secret"),
    RuntimeError("suburb=Bondi\nlooper.discover WARNING forged line lng=151.2743"),
    ConnectionError(f"Unable to connect to TypeDB server at {TYPEDB_ADDRESS}"),
    ConnectionError("connect failed: typedb-internal.example (port 1729)"),
    ConnectionError("dial tcp 10.0.0.5:1729: connection refused"),
    ConnectionError("typedb://admin:hunter2@typedb-internal.example:1729/localloop"),
    ValueError("could not convert -33.89 / 151.27 for Bondi"),
    OperationalError("SELECT * FROM businesses WHERE category LIKE ?",
                     ("%private-query%", -33.8915, 151.2743), Exception("password=secret")),
    TypeDBDriverException("[CXN01] Unable to connect to TypeDB server at "
                          f"{TYPEDB_ADDRESS}; user admin password hunter2"),
    TypeDBDriverException("no code here: category=private-query at 10.0.0.5:1729"),
    RuntimeError("no businesses near Bondi for private query"),
    RuntimeError("cache miss for 'Bondi' and Bondi's private stuff"),
    RuntimeError("auth token abcdefXYZ rejected; password: hunter then retry"),
    RuntimeError("login secretvalue failed for user admin"),
    RuntimeError("timeout " + "word " * 40 + "Bondi"),
], ids=["key-values", "newline-injection", "exact-address", "partial-address",
        "ip-address", "url-credentials", "coords-in-valueerror", "sqlalchemy-params",
        "typedb-coded", "typedb-uncoded", "plain-word-request-values",
        "quoted-request-values", "credential-keywords", "credential-plain-words",
        "long-message"])
def test_warning_never_leaks_request_values_or_secrets(client, db, caplog, monkeypatch, exc):
    text = _fail_discover(client, caplog, monkeypatch, exc)
    assert type(exc).__name__ in text
    assert "\n" not in text and "\r" not in text
    for leaked in FORBIDDEN:
        assert leaked not in text, f"{leaked!r} leaked into: {text}"
    assert "abcdefXYZ" not in text and "hunter" not in text
    assert len(text) < 250


@pytest.mark.parametrize("exc, detail", [
    (_GraphDown("typedb connection refused"), "typedb connection refused"),
    (ConnectionResetError("Connection reset by peer"), "Connection reset by peer"),
    (TimeoutError("timed out waiting for the graph"), "timed out waiting for the graph"),
    (ValueError(discover_route._NO_CENTER), "no center to search from"),
    (TypeDBDriverException(f"[CXN01] Unable to connect to TypeDB server at {TYPEDB_ADDRESS}"),
     "[CXN01] Unable to connect to TypeDB server at [redacted]"),
    (TypeDBDriverException("[TXN08] The transaction has been closed."),
     "[TXN08] The transaction has been closed."),
    (OperationalError("SELECT 1", ("private-query",), Exception("database is locked")),
     "database is locked (sqlalchemy error e3q8)"),
    (ConnectionError("dial tcp 10.0.0.5:1729: connection refused"),
     "dial tcp [redacted] connection refused"),
], ids=["benign-runtime", "benign-reset", "benign-timeout", "no-center", "typedb-coded",
        "typedb-closed", "sqlalchemy-orig", "mixed"])
def test_benign_message_survives(client, db, caplog, monkeypatch, exc, detail):
    """Useful diagnostics survive: plain words, TypeDB codes, the DB driver's message."""
    text = _fail_discover(client, caplog, monkeypatch, exc)
    assert text.endswith(f"{type(exc).__name__}: {detail}"), text


def test_plain_word_typedb_host_is_redacted(client, db, caplog, monkeypatch):
    """A one-word host (e.g. a Docker service name) is a connection detail too."""
    monkeypatch.setenv("TYPEDB_ADDRESS", "graphhost:1729")
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    monkeypatch.setattr(discover_route, "_graph_discover",
                        _raiser(ConnectionError("cannot resolve graphhost right now")))
    caplog.set_level(logging.WARNING, logger="looper.discover")
    assert client.get("/api/discover", params=REQUEST).json()["engine"] == "fallback"
    [record] = _warnings(caplog)
    assert record.getMessage().endswith("ConnectionError: cannot resolve [redacted] right now")


class _BadStr(RuntimeError):
    def __str__(self):
        raise RuntimeError("password=secret")


def test_unprintable_exception_still_falls_back(client, db, caplog, monkeypatch):
    text = _fail_discover(client, caplog, monkeypatch, _BadStr())
    assert "_BadStr" in text and "message withheld" in text and "secret" not in text


def test_real_graph_path_without_driver_logs_missing_module(client, db, caplog, monkeypatch):
    """The unpatched engine: typedb-driver is not installed in the lean backend."""
    try:
        import typedb  # noqa: F401
        pytest.skip("typedb driver installed; this checks the lean install")
    except ImportError:
        pass
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    monkeypatch.setenv("TYPEDB_ADDRESS", TYPEDB_ADDRESS)
    caplog.set_level(logging.WARNING, logger="looper.discover")
    assert client.get("/api/discover", params=REQUEST).json()["engine"] == "fallback"
    [record] = _warnings(caplog)
    assert record.getMessage().endswith("ModuleNotFoundError: missing module typedb")


def test_graph_disabled_logs_nothing(client, db, caplog):
    caplog.set_level(logging.WARNING, logger="looper.discover")
    resp = client.get("/api/discover", params={"suburb": "Bondi"})
    assert resp.status_code == 200
    assert resp.json()["engine"] == "fallback"
    assert not [r for r in caplog.records if r.name == "looper.discover"]

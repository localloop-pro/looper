"""Issue #152: a TypeDB graph failure in /api/discover must leave one warning
on the `looper.discover` logger while the transparent SQLite fallback and
response shape stay unchanged. The warning carries only the exception class
name and, for typedb.* exceptions, a "[CXN01]"-style error code. No exception
message text, traceback, request value or TypeDB address ever reaches it."""
import logging

import pytest
from sqlalchemy.exc import OperationalError

from models import Business
from routes import discover as discover_route

PREFIX = "discover graph engine failed, using fallback: "
REQUEST = {"suburb": "Bondi", "lat": -33.8915, "lng": 151.2743,
           "category": "private-query"}
TYPEDB_ADDRESS = "typedb-internal.example:1729"

# Request values and secret-like strings that must never reach the log.
FORBIDDEN = ("Bondi", "bondi", "-33.8915", "33.89", "151.2743", "151.27",
             "private", "query", "typedb-internal", "1729", "10.0.0.5",
             "hunter", "admin", "secret", "password", "example", "SELECT",
             "Ocean", "Street", "25", "authentication", "redacted", "withheld")


class _GraphDown(RuntimeError):
    pass


class TypeDBDriverException(Exception):
    """Stand-in for the TypeDB driver's exception (module is what matters)."""


TypeDBDriverException.__module__ = "typedb.common.exception"
TYPEDB_NAME = "typedb.common.exception.TypeDBDriverException"


class NotTypeDBException(Exception):
    """Same code-like message, but not a typedb.* exception."""


NotTypeDBException.__module__ = "typedbx.errors"


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
    assert record.exc_info is None and record.stack_info is None  # no traceback
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
    assert record.getMessage() == PREFIX + f"{_GraphDown.__module__}._GraphDown"


@pytest.mark.parametrize("exc, logged", [
    # The two review repros: free text around a credential or an address.
    (RuntimeError("authentication failed for password is hunter"), "RuntimeError"),
    (RuntimeError("failed for address 25 Ocean Street"), "RuntimeError"),
    (RuntimeError("category=private-query lat=-33.8915 password=secret"), "RuntimeError"),
    (RuntimeError("suburb=Bondi\nlooper.discover WARNING forged line lng=151.2743"),
     "RuntimeError"),
    (ConnectionError(f"Unable to connect to TypeDB server at {TYPEDB_ADDRESS}"),
     "ConnectionError"),
    (ConnectionError("dial tcp 10.0.0.5:1729: connection refused"), "ConnectionError"),
    (ConnectionError("typedb://admin:hunter2@typedb-internal.example:1729/localloop"),
     "ConnectionError"),
    (ValueError("no businesses near Bondi for private query"), "ValueError"),
    (OperationalError("SELECT * FROM businesses WHERE category LIKE ?",
                      ("%private-query%", -33.8915, 151.2743), Exception("password=secret")),
     "sqlalchemy.exc.OperationalError"),
    (TypeDBDriverException(f"[CXN01] Unable to connect to TypeDB server at {TYPEDB_ADDRESS}"
                           "; user admin password hunter2"), TYPEDB_NAME + " [CXN01]"),
    (TypeDBDriverException("[TXN08]\nWARNING forged line suburb=Bondi"),
     TYPEDB_NAME + " [TXN08]"),
    # Strict code match: only an exact [ABC12] at the very start counts.
    (TypeDBDriverException("category=private-query at 10.0.0.5:1729 [CXN01]"), TYPEDB_NAME),
    (TypeDBDriverException("[CXN1] Bondi"), TYPEDB_NAME),
    (TypeDBDriverException("[cxn01] Bondi"), TYPEDB_NAME),
    (TypeDBDriverException("[CXN012] Bondi"), TYPEDB_NAME),
    (TypeDBDriverException("[Bondi] password hunter"), TYPEDB_NAME),
    # A code-like message on a non-typedb exception is not logged at all.
    (NotTypeDBException("[CXN01] password hunter"), "typedbx.errors.NotTypeDBException"),
    (RuntimeError("[CXN01] Bondi"), "RuntimeError"),
], ids=["repro-password", "repro-address", "key-values", "newline-injection",
        "exact-address", "ip-address", "url-credentials", "plain-word-request-values",
        "sqlalchemy-params", "typedb-coded-with-secrets", "typedb-coded-newline",
        "typedb-code-not-at-start", "typedb-code-short", "typedb-code-lowercase",
        "typedb-code-long", "typedb-code-words", "typedb-lookalike-module",
        "builtin-with-code"])
def test_warning_logs_only_class_and_code(client, db, caplog, monkeypatch, exc, logged):
    text = _fail_discover(client, caplog, monkeypatch, exc)
    assert text == PREFIX + logged  # exact: nothing else from the exception
    for leaked in FORBIDDEN:
        assert leaked not in text, f"{leaked!r} leaked into: {text}"


class _BadStr(TypeDBDriverException):
    def __str__(self):
        raise RuntimeError("password=secret")


_BadStr.__module__ = "typedb.common.exception"


def test_unprintable_typedb_exception_still_falls_back(client, db, caplog, monkeypatch):
    text = _fail_discover(client, caplog, monkeypatch, _BadStr())
    assert text == PREFIX + "typedb.common.exception._BadStr"


def test_odd_class_name_is_not_logged(client, db, caplog, monkeypatch):
    """A class name is code, but check it strictly too."""
    odd = type("Bondi password=hunter\nforged", (RuntimeError,), {})
    text = _fail_discover(client, caplog, monkeypatch, odd("x"))
    assert text == PREFIX + "Exception"


def test_real_graph_path_without_driver_logs_class_only(client, db, caplog, monkeypatch):
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
    assert record.getMessage() == PREFIX + "ModuleNotFoundError"


def test_graph_disabled_logs_nothing(client, db, caplog):
    caplog.set_level(logging.WARNING, logger="looper.discover")
    resp = client.get("/api/discover", params={"suburb": "Bondi"})
    assert resp.status_code == 200
    assert resp.json()["engine"] == "fallback"
    assert not [r for r in caplog.records if r.name == "looper.discover"]

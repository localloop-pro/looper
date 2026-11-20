"""Issue #164: a TypeDB brain-sync failure after an accepted bridge event must
leave one public-safe warning on the `looper.ingest` logger (class name and
TypeDB code only) while the bridge response stays unchanged."""
import logging
import sys
import types

from routes import ingest as ingest_route
from tests.conftest import signed_post
from tests.test_ingest_card import PATH, sample_card_payload


class TypeDBDriverException(Exception):
    pass


TypeDBDriverException.__module__ = "typedb.common.exception"


def _fail_sync(monkeypatch, exc):
    fake = types.ModuleType("sync")

    def sync_business(**kwargs):
        raise exc

    fake.sync_business = sync_business
    monkeypatch.setitem(sys.modules, "sync", fake)


def _warnings(caplog):
    return [r for r in caplog.records
            if r.name == "looper.ingest" and r.levelno == logging.WARNING]


def test_brain_sync_failure_logs_one_public_safe_warning(client, db, caplog, monkeypatch):
    _fail_sync(monkeypatch, TypeDBDriverException(
        "[CXN01] Unable to connect to typedb-internal.example:1729 for Bondi Cafe"))
    caplog.set_level(logging.WARNING, logger="looper.ingest")

    resp = signed_post(client, PATH, sample_card_payload())

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "duplicate": False}
    [record] = _warnings(caplog)
    assert record.exc_info is None and record.stack_info is None
    msg = record.getMessage()
    assert "typedb.common.exception.TypeDBDriverException [CXN01]" in msg
    for secret in ("Bondi", "card-abc123", "typedb-internal", "1729",
                   "-33.89", "151.27", "Unable"):
        assert secret not in msg


def test_brain_sync_non_typedb_failure_logs_class_only(caplog, monkeypatch):
    _fail_sync(monkeypatch, RuntimeError("secret detail for Bondi Cafe"))
    caplog.set_level(logging.WARNING, logger="looper.ingest")

    ingest_route._brain_sync("card-1", "Bondi Cafe", "café", -33.89, 151.27, True)

    [record] = _warnings(caplog)
    assert "RuntimeError" in record.getMessage()
    assert "secret" not in record.getMessage() and "Bondi" not in record.getMessage()

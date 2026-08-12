"""Regression tests for TypeDB configuration defaults.

Coolify and the local shell can expose declared variables with an empty value.
The TypeDB driver rejects an empty address with ``invalid format``; blank values
must therefore behave the same as absent values across every brain entry point.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("module_name", "host_attr", "db_attr"),
    [
        ("brain.migrate", "DEFAULT_HOST", "DEFAULT_DB"),
        ("brain.seed_geo", "DEFAULT_HOST", "DEFAULT_DB"),
        ("brain.full_sync", "DEFAULT_HOST", "DEFAULT_TYPEDB_DB"),
        ("brain.sync", "_TYPEDB_HOST", "_TYPEDB_DB"),
    ],
)
def test_blank_typedb_env_uses_safe_defaults(
    monkeypatch, module_name: str, host_attr: str, db_attr: str
):
    monkeypatch.setenv("TYPEDB_ADDRESS", "")
    monkeypatch.setenv("TYPEDB_DB", "")

    module = importlib.import_module(module_name)
    module = importlib.reload(module)

    assert getattr(module, host_attr) == "localhost:1729"
    assert getattr(module, db_attr) == "localloop"


def test_full_sync_blank_sqlite_url_uses_repo_database(monkeypatch):
    monkeypatch.setenv("LOOPER_DB_URL", "")

    module = importlib.import_module("brain.full_sync")
    module = importlib.reload(module)

    assert module.DEFAULT_DB_URL.startswith("sqlite:///")
    assert module.DEFAULT_DB_URL.endswith("backend/data/looper.db")


def test_zero_coordinates_are_not_treated_as_missing(monkeypatch):
    """Latitude/longitude 0 are valid coordinates, not falsey missing data."""
    module = importlib.import_module("brain.sync")
    monkeypatch.setattr(module, "_TYPEDB_ENABLED", True)
    seen: list[tuple[float, float]] = []
    monkeypatch.setattr(
        module,
        "nearest_suburb",
        lambda lat, lng: seen.append((lat, lng)) or None,
    )

    # The deliberately failing driver path is swallowed by the additive sync
    # contract; this assertion only guards the coordinate-presence branch.
    monkeypatch.setattr(module, "_get_driver", lambda: (_ for _ in ()).throw(RuntimeError("stop")))
    assert module.sync_business("card-zero", "Zero", "other", 0.0, 0.0, True) is False
    assert seen == [(0.0, 0.0)]

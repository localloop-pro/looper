"""Opt-in TypeDB acceptance tests for F2.1/F2.2/F2.3.

Normal backend CI does not require Docker. Run the real graph contract with:

    docker run -d --rm --name looper-typedb-test \
      -p 127.0.0.1:1729:1729 vaticle/typedb:2.29.1
    RUN_TYPEDB_INTEGRATION=1 TYPEDB_ADDRESS=localhost:1729 \
      .venv/bin/python -m pytest -q tests/test_typedb_integration.py
"""
from __future__ import annotations

import importlib
import os
import uuid

import pytest

from tests.conftest import sample_deal_payload, signed_post
from models import Business


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_TYPEDB_INTEGRATION") != "1",
    reason="set RUN_TYPEDB_INTEGRATION=1 with a local TypeDB 2.x server",
)


@pytest.fixture()
def typedb_database(monkeypatch):
    from typedb.driver import TypeDB

    host = os.getenv("TYPEDB_ADDRESS") or "localhost:1729"
    db_name = f"looper_test_{uuid.uuid4().hex}"
    monkeypatch.setenv("TYPEDB_ADDRESS", host)
    monkeypatch.setenv("TYPEDB_DB", db_name)
    monkeypatch.setenv("TYPEDB_ENABLED", "true")

    from brain import migrate as migrate_module
    from brain.seed_geo import seed

    migration_log = migrate_module._log_path(host, db_name)
    try:
        migrate_module.migrate(host, db_name)
        seed(host, db_name)
        yield host, db_name
    finally:
        try:
            with TypeDB.core_driver(host) as driver:
                if driver.databases.contains(db_name):
                    driver.databases.get(db_name).delete()
        finally:
            migration_log.unlink(missing_ok=True)


def test_signed_ingest_syncs_business_and_graph_matches_fallback(
    client, db, typedb_database, monkeypatch
):
    host, db_name = typedb_database

    # sync.py snapshots its config at import time; reload after the fixture has
    # selected the isolated TypeDB database, just as a fresh backend process
    # reads its Coolify environment at startup.
    import brain.sync as brain_sync

    importlib.reload(brain_sync)

    # The ingest route imports `sync` from the brain directory for deployment
    # compatibility. Make that module resolve to the freshly configured copy.
    import sys

    monkeypatch.setitem(sys.modules, "sync", brain_sync)

    response = signed_post(
        client,
        "/api/ingest/hybridcard-deal",
        sample_deal_payload(
            eventId=f"evt-{uuid.uuid4()}",
            hybrid_card_id="typedb-card-1",
            deal_id="typedb-deal-1",
            business_name="TypeDB Bondi Cafe",
        ),
    )
    assert response.status_code == 200

    # Non-carded SQLite businesses are deliberately merged into the graph
    # result so enabling TypeDB cannot hide community listings.
    db.add(
        Business(
            name="Community Bondi Barber",
            category="café",
            suburb="Bondi",
            lat=-33.8910,
            lng=151.2745,
            is_active=True,
        )
    )
    db.commit()

    from typedb.driver import SessionType, TransactionType, TypeDB

    with TypeDB.core_driver(host) as driver:
        with driver.session(db_name, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                rows = list(
                    tx.query.get(
                        'match $b isa business_entity, has hybrid_card_id '
                        '"typedb-card-1", has name $name; '
                        '(contained: $b, container: $s) isa located_in; '
                        '$s has name $suburb; get $name, $suburb;'
                    )
                )
    assert len(rows) == 1
    assert rows[0].get("suburb").as_attribute().get_value() == "Bondi Beach"

    params = {"suburb": "Bondi", "radius_km": 5, "limit": 50}
    monkeypatch.setenv("TYPEDB_ENABLED", "false")
    fallback = client.get("/api/discover", params=params)
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    graph = client.get("/api/discover", params=params)

    assert fallback.status_code == graph.status_code == 200
    assert fallback.json()["engine"] == "fallback"
    assert graph.json()["engine"] == "graph"
    assert [r["name"] for r in graph.json()["results"]] == [
        r["name"] for r in fallback.json()["results"]
    ]

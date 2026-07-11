"""Shared fixtures for the looper backend test suite.

IMPORTANT: env vars are set BEFORE importing models — the SQLAlchemy engine
binds LOOPER_DB_URL at import time (models.py module level).
"""
import json
import os
import pathlib
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["HYBRIDCARD_INGEST_SECRET"] = "test-secret"
os.environ["HYBRIDCARD_KEY_IDS"] = "hc-1"
os.environ["LOOPER_DB_URL"] = f"sqlite:///{BACKEND}/data/test_looper.db"

import pytest  # noqa: E402
import models  # noqa: E402  (engine now bound to the test DB)
from services import bridge_hmac  # noqa: E402


@pytest.fixture()
def db():
    """Fresh schema per test."""
    models.Base.metadata.drop_all(models.engine)
    models.Base.metadata.create_all(models.engine)
    session = models.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def sample_deal_payload(**overrides) -> dict:
    """LooperIngestPayload sample (BRIDGE-CONTRACT-v1 §15 shape)."""
    payload = {
        "source": "hybridcard",
        "eventId": "evt-1",
        "hybrid_card_id": "card-abc123",
        "deal_id": "deal-xyz789",
        "business_name": "Bondi Cafe",
        "category": "café",
        "pin_type": "offering",
        "sub_type": "cafe",
        "title": "30% off",
        "short_description": "Lunch deal",
        "discount_size": 30,
        "lat": -33.8908,
        "lng": 151.2748,
        "hours": "9-5",
        "public_card_url": "https://bondi-cafe.hybridcard.ai",
        "active": True,
        "updated_at": "2026-07-11T00:00:00.000Z",
        "rank_boost": False,
    }
    payload.update(overrides)
    return payload


def signed_post(client, path, payload: dict, *, secret="test-secret", key_id="hc-1",
                ts_offset_ms=0, tamper=False, extra_headers=None, drop_headers=()):
    """POST a payload with X-HC-* headers signed the sender's way."""
    raw = json.dumps(payload).encode()
    ts = int(time.time() * 1000) + ts_offset_ms
    headers = bridge_hmac.sign(raw, secret, key_id, ts)
    if extra_headers:
        headers.update(extra_headers)
    for h in drop_headers:
        headers.pop(h, None)
    body = raw if not tamper else raw + b" "
    return client.post(path, content=body,
                       headers={**headers, "Content-Type": "application/json"})

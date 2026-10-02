"""F1.2 acceptance matrix — POST /api/ingest/hybridcard-card."""
import pytest

from models import BridgeEvent, Business, Deal
from tests.conftest import sample_deal_payload, signed_post

PATH = "/api/ingest/hybridcard-card"


def sample_card_payload(**overrides) -> dict:
    payload = {
        "event_kind": "card",
        "eventId": "card-evt-1",
        "hybrid_card_id": "card-abc123",
        "slug": "bondi-cafe",
        "business_name": "Bondi Cafe",
        "category": "café",
        "sub_type": "cafe",
        "lat": -33.8908,
        "lng": 151.2748,
        "hours": {"mon": "9-5"},  # T2 spec: object (deal payload uses string)
        "public_card_url": "https://bondi-cafe.hybridcard.ai",
        "archetype": "food",
        "status": "active",
        "active": True,
        "updated_at": "2026-07-11T00:00:00.000Z",
        "rank_boost": False,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("kwargs", [
    {"secret": "wrong-secret"},
    {"tamper": True},
    {"ts_offset_ms": -360_000},
    {"ts_offset_ms": 360_000},
    {"key_id": "hc-9"},
    {"drop_headers": ("X-HC-Signature",)},
    {"extra_headers": {"X-HC-Timestamp": "not-a-number"}},
])
def test_hmac_matrix_rejected(client, db, kwargs):
    resp = signed_post(client, PATH, sample_card_payload(), **kwargs)
    assert resp.status_code == 401
    assert db.query(Business).count() == 0


def test_card_upserted_creates_business(client, db):
    resp = signed_post(client, PATH, sample_card_payload())
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "duplicate": False}
    biz = db.query(Business).filter(Business.hybrid_card_id == "card-abc123").one()
    assert biz.source == "hybrid_card"
    assert biz.website == "https://bondi-cafe.hybridcard.ai"
    assert biz.is_active is True


def test_localhost_public_card_url_stored_as_is(client, db):
    """Local HybridCard emits http://localhost:3000/c/{slug} — ingest must not
    rewrite to *.hybridcard.ai or strip the URL."""
    local = "http://localhost:3000/c/bondi-cafe"
    resp = signed_post(client, PATH, sample_card_payload(public_card_url=local))
    assert resp.status_code == 200
    biz = db.query(Business).filter(Business.hybrid_card_id == "card-abc123").one()
    assert biz.website == local
    result = client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"][0]
    assert result["card_url"] == local


def test_event_replay_is_idempotent(client, db):
    signed_post(client, PATH, sample_card_payload())
    resp = signed_post(client, PATH, sample_card_payload())
    assert resp.json() == {"ok": True, "duplicate": True}
    assert db.query(Business).count() == 1
    assert db.query(BridgeEvent).count() == 1


def test_card_removed_hides_business_and_deals_from_search(client, db):
    # deal first (creates the business), then the card is unpublished
    signed_post(client, "/api/ingest/hybridcard-deal", sample_deal_payload())
    assert client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"]

    resp = signed_post(client, PATH, sample_card_payload(eventId="card-evt-2", active=False))
    assert resp.status_code == 200

    biz = db.query(Business).one()
    assert biz.is_active is False
    # deals untouched (card unpublish is not deal.removed)…
    assert db.query(Deal).one().active is True
    # …but the whole business is gone from search
    assert client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"] == []
    assert client.get("/api/businesses").json()["results"] == []


def test_reupsert_restores_business_in_search(client, db):
    signed_post(client, PATH, sample_card_payload())
    signed_post(client, PATH, sample_card_payload(eventId="card-evt-2", active=False))
    signed_post(client, PATH, sample_card_payload(eventId="card-evt-3", active=True))
    results = client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"]
    assert [r["name"] for r in results] == ["Bondi Cafe"]


def test_string_hours_also_tolerated(client, db):
    resp = signed_post(client, PATH, sample_card_payload(hours="9-5"))
    assert resp.status_code == 200

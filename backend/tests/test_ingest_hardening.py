"""Regression tests for the pre-push review findings (see PR + decisions.md):
out-of-order retries, fractional discounts, oversized bodies, NULL is_active.
"""
import time

from sqlalchemy import text

from models import Business, Deal
from services import bridge_hmac
from tests.conftest import sample_deal_payload, signed_post
from tests.test_ingest_card import sample_card_payload

DEAL_PATH = "/api/ingest/hybridcard-deal"
CARD_PATH = "/api/ingest/hybridcard-card"

T1 = "2026-07-11T00:00:00.000Z"  # older
T2 = "2026-07-11T01:00:00.000Z"  # newer


def test_stale_deal_retry_cannot_resurrect_removed_deal(client, db):
    # publish (T1) → remove (T2) → stale retry of an upsert with T1 arrives
    # last (new eventId, fresh signature — exactly what the outbox does)
    signed_post(client, DEAL_PATH, sample_deal_payload(eventId="evt-1", updated_at=T1))
    signed_post(client, DEAL_PATH, sample_deal_payload(eventId="evt-2", updated_at=T2,
                                                       active=False))
    resp = signed_post(client, DEAL_PATH, sample_deal_payload(eventId="evt-1-retry",
                                                              updated_at=T1,
                                                              title="stale title"))
    assert resp.status_code == 200
    assert resp.json().get("stale") is True
    deal = db.query(Deal).one()
    assert deal.active is False  # still removed
    assert deal.title != "stale title"


def test_stale_card_retry_cannot_resurrect_removed_business(client, db):
    signed_post(client, CARD_PATH, sample_card_payload(eventId="c1", updated_at=T1))
    signed_post(client, CARD_PATH, sample_card_payload(eventId="c2", updated_at=T2,
                                                       active=False))
    resp = signed_post(client, CARD_PATH, sample_card_payload(eventId="c1-retry",
                                                              updated_at=T1,
                                                              business_name="Stale Name"))
    assert resp.status_code == 200
    biz = db.query(Business).one()
    assert biz.is_active is False
    assert biz.name != "Stale Name"
    assert client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"] == []


def test_newer_event_after_removal_reactivates(client, db):
    # sanity: the gate only blocks OLDER events, not legitimate newer ones
    T3 = "2026-07-11T02:00:00.000Z"
    signed_post(client, DEAL_PATH, sample_deal_payload(eventId="evt-1", updated_at=T2,
                                                       active=False))
    signed_post(client, DEAL_PATH, sample_deal_payload(eventId="evt-2", updated_at=T3,
                                                       title="fresh title"))
    deal = db.query(Deal).one()
    assert deal.active is True
    assert deal.title == "fresh title"


def test_fractional_discount_accepted(client, db):
    # sender contract type is number; zod allows 12.5 — must not 422
    resp = signed_post(client, DEAL_PATH, sample_deal_payload(discount_size=12.5))
    assert resp.status_code == 200
    assert db.query(Deal).one().discount_size == 12.5


def test_oversized_body_rejected_413(client, db):
    payload = sample_deal_payload(short_description="x" * 100_000)
    resp = signed_post(client, DEAL_PATH, payload)
    assert resp.status_code == 413
    assert db.query(Deal).count() == 0


def test_oversized_declared_content_length_rejected(client):
    raw = b"{}"
    headers = bridge_hmac.sign(raw, "test-secret", "hc-1", int(time.time() * 1000))
    resp = client.post(DEAL_PATH, content=raw,
                       headers={**headers, "Content-Type": "application/json",
                                "Content-Length": str(10_000_000)})
    assert resp.status_code == 413


def test_null_is_active_row_stays_visible_in_search(client, db):
    # legacy rows that predate the column may hold NULL — IS NOT false keeps them
    db.execute(text(
        "INSERT INTO businesses (name, category, suburb, is_active) "
        "VALUES ('Null Cafe', 'café', 'Bondi', NULL)"))
    db.commit()
    results = client.get("/api/search", params={"q": "Null Cafe"}).json()["results"]
    assert [r["name"] for r in results] == ["Null Cafe"]

"""F1.1 acceptance matrix — POST /api/ingest/hybridcard-deal."""
from models import BridgeEvent, Business, Deal
from tests.conftest import sample_deal_payload, signed_post

PATH = "/api/ingest/hybridcard-deal"


def counts(db):
    return (db.query(Business).count(), db.query(Deal).count(),
            db.query(BridgeEvent).count())


def test_valid_payload_creates_rows(client, db):
    resp = signed_post(client, PATH, sample_deal_payload())
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "duplicate": False}

    biz = db.query(Business).filter(Business.hybrid_card_id == "card-abc123").one()
    assert biz.source == "hybrid_card"
    assert biz.name == "Bondi Cafe"
    assert biz.category == "café"
    assert biz.is_active is True

    deal = db.query(Deal).filter(Deal.deal_id == "deal-xyz789").one()
    assert deal.business_id == biz.id
    assert deal.title == "30% off"
    assert deal.discount_size == 30
    assert deal.active is True
    assert db.query(BridgeEvent).filter(BridgeEvent.event_id == "evt-1").count() == 1


def test_event_replay_is_idempotent(client, db):
    assert signed_post(client, PATH, sample_deal_payload()).status_code == 200
    resp = signed_post(client, PATH, sample_deal_payload())  # same eventId again
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "duplicate": True}
    assert counts(db) == (1, 1, 1)


def test_same_deal_new_event_updates_in_place(client, db):
    signed_post(client, PATH, sample_deal_payload())
    resp = signed_post(client, PATH, sample_deal_payload(eventId="evt-2", title="40% off",
                                                         discount_size=40))
    assert resp.status_code == 200
    assert resp.json()["duplicate"] is False
    assert counts(db) == (1, 1, 2)
    deal = db.query(Deal).one()
    assert deal.title == "40% off"
    assert deal.discount_size == 40


def test_bad_signature_rejected(client, db):
    resp = signed_post(client, PATH, sample_deal_payload(), secret="wrong-secret")
    assert resp.status_code == 401
    assert counts(db) == (0, 0, 0)


def test_tampered_body_rejected(client, db):
    resp = signed_post(client, PATH, sample_deal_payload(), tamper=True)
    assert resp.status_code == 401
    assert counts(db) == (0, 0, 0)


def test_stale_and_future_timestamps_rejected(client, db):
    for offset in (-360_000, 360_000):  # ±6 min, outside the ±5 min window
        resp = signed_post(client, PATH, sample_deal_payload(), ts_offset_ms=offset)
        assert resp.status_code == 401
    assert counts(db) == (0, 0, 0)


def test_unknown_key_id_rejected(client, db):
    resp = signed_post(client, PATH, sample_deal_payload(), key_id="hc-9")
    assert resp.status_code == 401
    assert counts(db) == (0, 0, 0)


def test_missing_headers_rejected(client, db):
    for header in ("X-HC-Signature", "X-HC-Key-Id", "X-HC-Timestamp"):
        resp = signed_post(client, PATH, sample_deal_payload(), drop_headers=(header,))
        assert resp.status_code == 401
    assert counts(db) == (0, 0, 0)


def test_non_numeric_timestamp_rejected(client, db):
    resp = signed_post(client, PATH, sample_deal_payload(),
                       extra_headers={"X-HC-Timestamp": "not-a-number"})
    assert resp.status_code == 401
    assert counts(db) == (0, 0, 0)


def test_deal_removed_deactivates_never_deletes(client, db):
    signed_post(client, PATH, sample_deal_payload())
    resp = signed_post(client, PATH, sample_deal_payload(eventId="evt-2", active=False))
    assert resp.status_code == 200
    assert counts(db) == (1, 1, 2)  # row still there
    assert db.query(Deal).one().active is False


def test_removed_before_upserted_is_tolerated(client, db):
    # out-of-order replay: deal.removed for a never-seen deal
    resp = signed_post(client, PATH, sample_deal_payload(active=False))
    assert resp.status_code == 200
    deal = db.query(Deal).one()
    assert deal.active is False


def test_malformed_json_with_valid_signature_422(client, db):
    import time
    from services import bridge_hmac
    raw = b"{not json"
    headers = bridge_hmac.sign(raw, "test-secret", "hc-1", int(time.time() * 1000))
    resp = client.post(PATH, content=raw,
                       headers={**headers, "Content-Type": "application/json"})
    assert resp.status_code == 422  # non-2xx → sender retries then dead-letters
    assert counts(db) == (0, 0, 0)

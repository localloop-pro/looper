"""#36 — card-URL events that reach the DEAL receiver.

HybridCard picks the card URL as
`LOOPER_CARD_INGEST_URL || LOOPER_INGEST_URL` (hybridcard-v2
src/lib/bridge/outbox.ts#L268-L270). With only LOOPER_INGEST_URL set, every
card.* and partnership.* event is POSTed to /api/ingest/hybridcard-deal.

The fix belongs to the sender. Looper's side: keep answering non-2xx (no
silent re-dispatch that would hide the misconfiguration), write nothing,
leave the eventId unburned, and name the cause in the 422 detail and the
bridge trace so an operator can see it.
"""
import json
import logging

import pytest

from models import BridgeEvent, Business, Deal
from services import correlation
from tests.conftest import sample_deal_payload, signed_post
from tests.test_ingest_card import sample_card_payload
from tests.test_ingest_partnership_mismatch import sender_partnership_payload

DEAL_PATH = "/api/ingest/hybridcard-deal"
CARD_PATH = "/api/ingest/hybridcard-card"
MISROUTED = ("misrouted: card event sent to the deal receiver; set "
             "LOOPER_CARD_INGEST_URL to /api/ingest/hybridcard-card")


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture()
def trace(monkeypatch):
    monkeypatch.delenv("LOOPER_TRACE_LOG", raising=False)
    handler = _Capture()
    correlation.logger.addHandler(handler)
    yield handler
    correlation.logger.removeHandler(handler)


def bridge_records(handler):
    return [r for r in map(json.loads, handler.lines) if r["kind"] == "bridge"]


@pytest.mark.parametrize("payload, event_type", [
    (sample_card_payload(), "card.upserted"),
    (sample_card_payload(active=False, status="draft"), "card.removed"),
    (sender_partnership_payload(), "partnership.upserted"),
    (sender_partnership_payload(removed=True), "partnership.removed"),
])
def test_card_url_event_at_deal_receiver_is_named_422(client, db, trace,
                                                     payload, event_type):
    resp = signed_post(client, DEAL_PATH, payload)
    assert resp.status_code == 422  # sender retries/dead-letters: visible, not silent
    assert resp.json() == {"detail": MISROUTED}
    assert db.query(BridgeEvent).count() == 0
    assert db.query(Business).count() == 0
    assert db.query(Deal).count() == 0
    (rec,) = bridge_records(trace)
    assert (rec["receiver"], rec["outcome"], rec["event_type"]) == \
        ("hybridcard-deal", "misrouted", event_type)
    # Rejections never log the eventId or any payload field (no PII).
    assert rec["event_id"] is None
    assert "Bondi Cafe" not in "\n".join(trace.lines)


def test_misrouted_card_still_lands_once_sent_to_card_receiver(client, db):
    """eventId is not burned by the 422, so the sender's retry to the right
    URL is processed, not swallowed as a duplicate."""
    payload = sample_card_payload()
    assert signed_post(client, DEAL_PATH, payload).status_code == 422
    resp = signed_post(client, CARD_PATH, payload)
    assert resp.json() == {"ok": True, "duplicate": False}
    assert db.query(Business).filter_by(hybrid_card_id="card-abc123").one().is_active


def test_misrouted_card_removed_deactivates_once_correctly_routed(client, db):
    signed_post(client, CARD_PATH, sample_card_payload())
    removed = sample_card_payload(eventId="card-evt-2", active=False, status="draft",
                                  updated_at="2026-07-12T00:00:00.000Z")
    assert signed_post(client, DEAL_PATH, removed).status_code == 422
    biz = db.query(Business).filter_by(hybrid_card_id="card-abc123").one()
    assert biz.is_active is True  # the misrouted unpublish changed nothing
    assert signed_post(client, CARD_PATH, removed).status_code == 200
    db.refresh(biz)
    assert biz.is_active is False  # deactivated, never deleted
    assert db.query(Business).count() == 1


@pytest.mark.parametrize("body", [
    {"eventId": "x"},                                 # no event_kind
    {"eventId": "x", "event_kind": "deal"},           # broken deal stays generic
    {"eventId": "x", "event_kind": ["card"]},         # odd type, no crash
])
def test_other_bad_deal_bodies_keep_generic_422(client, db, trace, body):
    resp = signed_post(client, DEAL_PATH, body)
    assert resp.status_code == 422
    assert resp.json() == {"detail": "invalid payload"}
    assert [r["outcome"] for r in bridge_records(trace)] == ["invalid_payload"]


def test_non_object_json_keeps_generic_422(client, db):
    resp = signed_post(client, DEAL_PATH, ["card"])
    assert resp.status_code == 422
    assert resp.json() == {"detail": "invalid payload"}


def test_misrouted_check_runs_after_hmac(client, db, trace):
    resp = signed_post(client, DEAL_PATH, sample_card_payload(), secret="wrong-secret")
    assert resp.status_code == 401
    assert [r["outcome"] for r in bridge_records(trace)] == ["unauthorized"]


def test_real_deal_still_processed(client, db):
    resp = signed_post(client, DEAL_PATH, sample_deal_payload())
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "duplicate": False}

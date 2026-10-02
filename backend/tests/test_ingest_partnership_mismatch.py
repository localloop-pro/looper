"""#23 — characterise today's partnership.* mismatch at the card receiver.

HybridCard's enqueuePartnershipEvents (hybridcard-v2 src/lib/bridge/outbox.ts)
sends partnership.upserted / partnership.removed to LOOPER_CARD_INGEST_URL,
i.e. POST /api/ingest/hybridcard-card. That payload has no hybrid_card_id,
business_name or category, so HybridCardCardPayload rejects it with 422 and
the sender dead-letters after 6 retries.

These tests pin the current behaviour (signed, rejected, nothing written) so
whichever option the owner picks on #23 changes them on purpose:
(a) sender stops -> tests stay; (b) new /ingest/hybridcard-partnership
receiver -> add its own tests, these stay for the card route.
"""
import pytest

from models import BridgeEvent, Business
from tests.conftest import signed_post

PATH = "/api/ingest/hybridcard-card"


def sender_partnership_payload(removed: bool = False) -> dict:
    """Byte-for-byte the shape enqueuePartnershipEvents builds."""
    return {
        "source": "hybridcard",
        "eventId": "partnership-evt-1",
        "event_kind": "partnership",
        "requester_card_id": "card-req-1",
        "partner_card_id": "card-par-2",
        "active": not removed,
        "updated_at": "2026-10-02T00:00:00.000Z",
        "rank_boost": False,
    }


@pytest.mark.parametrize("removed", [False, True])
def test_partnership_event_rejected_by_card_receiver(client, db, removed):
    resp = signed_post(client, PATH, sender_partnership_payload(removed))
    assert resp.status_code == 422
    assert resp.json() == {"detail": "invalid payload"}
    # Nothing recorded: no business, and the eventId is not burned, so a
    # future receiver can still accept it if the owner chooses to replay.
    assert db.query(Business).count() == 0
    assert db.query(BridgeEvent).count() == 0


def test_partnership_event_unsigned_is_401_not_422(client, db):
    """HMAC is checked before parsing — a bad signature never reaches the schema."""
    resp = signed_post(client, PATH, sender_partnership_payload(), secret="wrong-secret")
    assert resp.status_code == 401
    assert db.query(BridgeEvent).count() == 0

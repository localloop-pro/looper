"""looper#84 — caller-supplied `intent` and `session` must never carry PII
into training_log. Both are public query params on /api/search and
/api/discover; training/export.py ships these rows for fine-tuning."""
import pytest

from models import Business, TrainingLog
from services.telemetry import clean_intent, clean_session_id, log_query

ENDPOINTS = [
    ("/api/search", {"q": "cafe"}),
    ("/api/discover", {"suburb": "Bondi"}),
]


@pytest.fixture()
def biz(db):
    b = Business(name="Gertrude & Alice", category="café", suburb="Bondi Beach",
                 lat=-33.8893, lng=151.2735, is_active=True)
    db.add(b)
    db.commit()
    return b


def _only_row(db):
    rows = db.query(TrainingLog).all()
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("path,params", ENDPOINTS)
class TestEndpointsStoreSafeValues:
    def test_email_intent_and_mobile_session_are_dropped(self, client, db, biz, path, params):
        resp = client.get(path, params={**params, "intent": "me@example.com",
                                        "session": "0412 345 678"})
        assert resp.status_code == 200
        row = _only_row(db)
        assert row.intent == "other"
        assert row.session_id is None

    def test_mixed_case_known_intent_is_lowercased(self, client, db, biz, path, params):
        client.get(path, params={**params, "intent": "Voice"})
        assert _only_row(db).intent == "voice"

    def test_normal_values_stored_unchanged(self, client, db, biz, path, params):
        client.get(path, params={**params, "intent": "business",
                                 "session": "a1B2-c3_d4"})
        row = _only_row(db)
        assert row.intent == "business"
        assert row.session_id == "a1B2-c3_d4"

    def test_unbroken_mobile_session_is_dropped(self, client, db, biz, path, params):
        # Fits the opaque-id shape but is still a phone number.
        client.get(path, params={**params, "session": "0412345678"})
        assert _only_row(db).session_id is None

    def test_response_unchanged_by_dirty_telemetry(self, client, db, biz, path, params):
        clean = client.get(path, params=params).json()
        dirty = client.get(path, params={**params, "intent": "me@example.com",
                                         "session": "0412 345 678"}).json()
        assert clean == dirty


def test_default_intents_still_stored(client, db, biz):
    client.get("/api/search", params={"q": "cafe"})
    client.get("/api/discover", params={"suburb": "Bondi"})
    assert sorted(r.intent for r in db.query(TrainingLog).all()) == ["discover", "search"]


class TestCleaners:
    @pytest.mark.parametrize("raw,want", [
        ("search", "search"), ("discover", "discover"), ("business", "business"),
        ("voice", "voice"), ("VOICE", "voice"), ("  voice ", "voice"),
        ("map_pan", "map_pan"), ("a-b", "a-b"),
        ("me@example.com", "other"), ("0412345678", "other"),
        ("call bill", "other"), ("1search", "other"), ("x" * 33, "other"),
        ("", None), (None, None),
    ])
    def test_clean_intent(self, raw, want):
        assert clean_intent(raw) == want

    @pytest.mark.parametrize("raw,want", [
        ("sess-1", "sess-1"), ("a" * 64, "a" * 64),
        ("3f2b9c1e-8d4a-4e7b-9f00-1a2b3c4d5e6f", "3f2b9c1e-8d4a-4e7b-9f00-1a2b3c4d5e6f"),
        ("a" * 65, None), ("me@example.com", None), ("0412 345 678", None),
        ("0412345678", None), ("61412345678", None), ("has space", None),
        ("", None), (None, None),
    ])
    def test_clean_session_id(self, raw, want):
        assert clean_session_id(raw) == want

    def test_non_string_inputs_never_raise(self):
        assert clean_intent(123) == "other"
        assert clean_session_id(object()) is None


def test_log_query_never_raises_on_bad_session():
    class Boom:
        def add(self, _):
            raise RuntimeError("db down")

        def rollback(self):
            raise RuntimeError("still down")

    log_query(Boom(), "cafe", intent="me@example.com", session_id="0412 345 678")

"""looper#84 — caller-supplied `intent` / `session` must not carry PII into
training_log. Both are public query params on /api/search and /api/discover;
`training/export.py` ships these rows for fine-tuning."""
import pytest

from models import Business, TrainingLog
from services.telemetry import clean_intent, clean_session_id, log_query


def _biz(db):
    db.add(Business(name="Gertrude & Alice", category="café", suburb="Bondi Beach",
                    lat=-33.8893, lng=151.2735, is_active=True))
    db.commit()


ENDPOINTS = [
    ("/api/search", {"q": "cafe"}),
    ("/api/discover", {"suburb": "Bondi"}),
]


@pytest.mark.parametrize("path,base", ENDPOINTS)
class TestEndpointsStoreCleanLabels:
    def _row(self, client, db, path, base, **params):
        _biz(db)
        resp = client.get(path, params={**base, **params})
        assert resp.status_code == 200
        rows = db.query(TrainingLog).all()
        assert len(rows) == 1
        return rows[0]

    def test_email_intent_and_mobile_session_dropped(self, client, db, path, base):
        row = self._row(client, db, path, base,
                        intent="me@example.com", session="0412 345 678")
        assert row.intent == "other"
        assert row.session_id is None

    def test_intent_lowercased(self, client, db, path, base):
        row = self._row(client, db, path, base, intent="Voice")
        assert row.intent == "voice"

    def test_known_intent_and_normal_session_unchanged(self, client, db, path, base):
        row = self._row(client, db, path, base,
                        intent="business", session="sess-1_AbC9")
        assert row.intent == "business"
        assert row.session_id == "sess-1_AbC9"

    def test_default_intent_still_recorded(self, client, db, path, base):
        row = self._row(client, db, path, base)
        assert row.intent == path.rsplit("/", 1)[-1]  # "search" / "discover"
        assert row.session_id is None


class TestCleanIntent:
    @pytest.mark.parametrize("value", ["search", "discover", "business", "voice"])
    def test_known_callers_pass(self, value):
        assert clean_intent(value) == value

    @pytest.mark.parametrize("value", [
        "me@example.com", "0412345678", "call bill", "a" * 33, "9lives",
        "voice\nx", "été", "search;drop",
    ])
    def test_non_slugs_become_other(self, value):
        assert clean_intent(value) == "other"

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_missing_stays_none(self, value):
        assert clean_intent(value) is None

    def test_whitespace_trimmed(self):
        assert clean_intent(" Search ") == "search"


class TestCleanSessionId:
    @pytest.mark.parametrize("value", ["sess-1", "abc_DEF-123", "a" * 64,
                                       "3f2b9c1e-7d4a-4e8b-9f00-112233445566"])
    def test_opaque_ids_pass(self, value):
        assert clean_session_id(value) == value

    @pytest.mark.parametrize("value", [
        "me@example.com", "0412 345 678", "0412345678", "+61412345678",
        "61412345678", "a" * 65, "has space", "bill.smith", None, "",
    ])
    def test_unsafe_ids_become_none(self, value):
        assert clean_session_id(value) is None


def test_log_query_never_raises_on_odd_types(db):
    log_query(db, "cafe", intent=12345, session_id=object())
    row = db.query(TrainingLog).one()
    assert row.intent == "other"
    assert row.session_id is None

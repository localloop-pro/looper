"""F2.3 /api/discover (fallback engine) + F2.5 telemetry tests."""
from datetime import datetime, timezone

from models import Business, Review, TrainingLog, User
from services.telemetry import scrub_pii


def _biz(db, **kw):
    defaults = dict(
        name="Gertrude & Alice",
        category="café",
        suburb="Bondi Beach",
        lat=-33.8893,
        lng=151.2735,
        is_active=True,
    )
    defaults.update(kw)
    b = Business(**defaults)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def _review(db, business_id, rating=5):
    user = db.query(User).first()
    if not user:
        user = User(first_name="Test", mobile_number="0400000000", join_code="T1T2T3")
        db.add(user)
        db.commit()
        db.refresh(user)
    r = Review(business_id=business_id, user_id=user.id, rating=rating,
               review_text="Lovely spot, great coffee and staff.", is_public=True,
               created_at=datetime.now(timezone.utc))
    db.add(r)
    db.commit()
    return r


class TestDiscoverFallback:
    def test_suburb_discover_fallback_engine(self, client, db):
        _biz(db)
        resp = client.get("/api/discover", params={"suburb": "Bondi"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["engine"] == "fallback"
        assert [r["name"] for r in body["results"]] == ["Gertrude & Alice"]

    def test_category_filter_accent_folded(self, client, db):
        _biz(db)
        _biz(db, name="Bondi Physio", category="health")
        body = client.get("/api/discover",
                          params={"suburb": "Bondi", "category": "cafe"}).json()
        assert [r["name"] for r in body["results"]] == ["Gertrude & Alice"]

    def test_radius_excludes_far_businesses(self, client, db):
        _biz(db)
        _biz(db, name="Byron Cafe", suburb="Byron Bay", lat=-28.6474, lng=153.6120)
        body = client.get("/api/discover",
                          params={"suburb": "Bondi", "radius_km": 5}).json()
        names = [r["name"] for r in body["results"]]
        assert "Byron Cafe" not in names and "Gertrude & Alice" in names

    def test_reviewed_business_ranks_first(self, client, db):
        quiet = _biz(db, name="Quiet Cafe", lat=-33.8909, lng=151.2744)
        loved = _biz(db, name="Loved Cafe", lat=-33.8950, lng=151.2700)
        _review(db, loved.id)
        body = client.get("/api/discover", params={"suburb": "Bondi"}).json()
        assert body["results"][0]["name"] == "Loved Cafe"
        assert body["results"][0]["review_count"] == 1
        assert quiet.name in [r["name"] for r in body["results"]]

    def test_unknown_suburb_falls_back_to_name_match(self, client, db):
        _biz(db, suburb="Newtown", lat=None, lng=None)
        body = client.get("/api/discover", params={"suburb": "Newtown"}).json()
        assert body["engine"] == "fallback"
        assert len(body["results"]) == 1


class TestTelemetry:
    def test_search_writes_training_log(self, client, db):
        _biz(db)
        client.get("/api/search", params={"q": "cafe", "intent": "search",
                                          "session": "sess-1"})
        rows = db.query(TrainingLog).all()
        assert len(rows) == 1
        assert rows[0].query_text == "cafe"
        assert rows[0].intent == "search"
        assert rows[0].session_id == "sess-1"
        assert "Gertrude & Alice" in (rows[0].response_text or "")

    def test_discover_writes_training_log(self, client, db):
        _biz(db)
        client.get("/api/discover", params={"suburb": "Bondi"})
        rows = db.query(TrainingLog).all()
        assert len(rows) == 1
        assert rows[0].intent == "discover"

    def test_pii_scrubbed_before_storage(self, client, db):
        _biz(db)
        client.get("/api/search", params={
            "q": "cafe for bill@example.com call 0412 345 678"})
        row = db.query(TrainingLog).first()
        assert "bill@example.com" not in row.query_text
        assert "0412" not in row.query_text
        assert "[email]" in row.query_text and "[mobile]" in row.query_text

    def test_scrub_pii_variants(self):
        assert scrub_pii("email me at a.b+c@d-e.com.au ok") == "email me at [email] ok"
        assert scrub_pii("call +61 412 345 678 now") == "call [mobile] now"
        assert scrub_pii("call 0412345678") == "call [mobile]"
        assert scrub_pii(None) is None

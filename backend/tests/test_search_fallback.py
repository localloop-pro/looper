"""looper#73: one widened pass when nothing is in range, and honest messages.

The Jarvis dock searches 1.5 km around the map centre and the production
brain is sparse, so a match 3-4 km away used to come back as []. Now the
same candidates are filtered once more with FALLBACK_KM (default 10) and the
response carries ``widened_to_km``. The sort never changes.
"""
import pytest
from sqlalchemy import event

import models
import routes.search
from models import Business, Review, User
from tests.conftest import sample_deal_payload, signed_post

# Bondi Beach. 0.036 deg of latitude is ~4.0 km, 0.1 deg is ~11 km.
LAT, LNG = -33.8908, 151.2748


def _biz(db, name, lat, *, category="vet", source="manual", reviews=0):
    b = Business(name=name, category=category, suburb="Eastern Suburbs",
                 lat=lat, lng=LNG, source=source, is_active=True)
    db.add(b)
    db.flush()
    if reviews:
        user = User(first_name="Tester", mobile_number=f"04000001{b.id:02d}")
        db.add(user)
        db.flush()
        for i in range(reviews):
            db.add(Review(business_id=b.id, user_id=user.id, rating=4,
                          review_text=f"Kind staff, visit number {i + 1} went well."))
    db.commit()
    return b


def _search(client, **params):
    base = {"q": "vet", "lat": LAT, "lng": LNG, "radius_km": 1.5}
    base.update(params)
    resp = client.get("/api/search", params=base)
    assert resp.status_code == 200
    return resp.json()


def test_default_fallback_is_10_km():
    assert routes.search.FALLBACK_KM == 10.0


def test_in_radius_hit_runs_no_fallback(client, db):
    _biz(db, "Close Vet", LAT - 0.005)  # ~0.6 km
    _biz(db, "Far Vet", LAT - 0.036)    # ~4 km: outside, and not added
    data = _search(client)
    assert [r["name"] for r in data["results"]] == ["Close Vet"]
    assert data["widened_to_km"] is None
    assert "Nothing within" not in data["message"]


def test_zero_in_radius_widens_to_nearest_match(client, db):
    _biz(db, "Coogee Vet", LAT - 0.036)  # ~4 km
    data = _search(client)
    assert [r["name"] for r in data["results"]] == ["Coogee Vet"]
    assert data["widened_to_km"] == 10
    assert data["total_results"] == 1
    assert data["message"].startswith(
        "Nothing within 1.5 km for 'vet'. The nearest match is 4 km away.")


def test_nothing_within_fallback_is_an_honest_empty_answer(client, db):
    _biz(db, "Distant Vet", LAT - 0.1)  # ~11 km
    data = _search(client)
    assert data["results"] == []
    assert data["widened_to_km"] == 10
    assert data["message"] == "No one's listed for 'vet' within 10 km yet."


def test_no_location_means_no_fallback(client, db):
    data = client.get("/api/search", params={"q": "zzzqqq"}).json()
    assert data["results"] == []
    assert data["widened_to_km"] is None
    assert data["message"] == "No one's listed for 'zzzqqq' near here yet."


def test_fallback_never_smaller_than_radius(client, db, monkeypatch):
    monkeypatch.setattr(routes.search, "FALLBACK_KM", 2.0)
    _biz(db, "Coogee Vet", LAT - 0.036)
    data = _search(client, radius_km=3)
    assert data["results"] == []
    assert data["widened_to_km"] is None


def test_fallback_reuses_the_candidate_query(client, db):
    """At most one widened pass, and it costs no second businesses query."""
    _biz(db, "Coogee Vet", LAT - 0.036)
    statements = []

    def count(conn, cursor, statement, *args):
        if "FROM businesses" in statement:
            statements.append(statement)

    event.listen(models.engine, "before_cursor_execute", count)
    try:
        data = _search(client)
    finally:
        event.remove(models.engine, "before_cursor_execute", count)
    assert data["widened_to_km"] == 10
    assert len(statements) == 1


def test_fallback_never_reorders_by_deal_source_or_rank_boost(client, db):
    """Widened results use the same sort: reviews beat a 90% deal, a
    HybridCard source, a forced rank_boost and being closer."""
    _biz(db, "Reviewed Vet", LAT - 0.045, reviews=3)  # ~5 km, 3 reviews
    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(business_name="Deal Vet", category="vet",
                                           sub_type="vet", discount_size=90,
                                           rank_boost=True, lat=LAT - 0.027,
                                           lng=LNG))  # ~3 km, 0 reviews
    assert resp.status_code == 200
    data = _search(client)
    assert data["widened_to_km"] == 10
    names = [r["name"] for r in data["results"]]
    assert names == ["Reviewed Vet", "Deal Vet"]
    # the nearest is still reported honestly, even though it ranks second
    assert "The nearest match is 3 km away." in data["message"]


@pytest.mark.parametrize("n", [0, 1, 2])
def test_messages_are_plain_and_never_invite_writes(client, db, n):
    for i in range(n):
        _biz(db, f"Vet {i}", LAT - 0.002 * (i + 1))
    msg = _search(client)["message"]
    assert "<" not in msg and ">" not in msg
    lowered = msg.lower()
    assert "most reviewed first" not in lowered
    assert "first to add" not in lowered
    assert "add one" not in lowered
    if n == 2:
        assert "best match first, then most community reviews, then nearest" in msg

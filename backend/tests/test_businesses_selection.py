"""#121: select the eligible, review-ranked page in disposable SQLite."""
import pytest
from sqlalchemy import event

import models
from models import Business, Review


def add(db, name, **kw):
    row = Business(name=name, category="café", lat=-33.89, lng=151.27, **kw)
    db.add(row)
    db.flush()
    return row


@pytest.mark.parametrize("limit", [1, 50])
def test_distant_prefix_does_not_hide_eligible_page(client, db, limit):
    for i in range(50):
        row = add(db, f"far-{i}")
        row.lat = -35
    eligible = [add(db, f"near-{i}") for i in range(55)]
    db.commit()
    response = client.get("/api/businesses", params=dict(
        category="café", lat=-33.89, lng=151.27, radius_km=5, limit=limit))
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == len(data["results"]) == limit
    assert [r["id"] for r in data["results"]] == [r.id for r in eligible[:limit]]
    assert all(r["distance_km"] == 0 for r in data["results"])


@pytest.mark.parametrize("lat,lng", [(0, 0), (0, 151.27), (-33.89, 0)])
def test_zero_coordinates_and_missing_policy(client, db, lat, lng):
    near = add(db, "coincident")
    near.lat, near.lng = lat, lng
    far = add(db, "far")
    far.lat, far.lng = lat + 1, lng
    missing = add(db, "unknown")
    missing.lat = None
    db.commit()
    rows = client.get("/api/businesses", params=dict(lat=lat, lng=lng)).json()["results"]
    assert [r["id"] for r in rows] == [near.id, missing.id]
    assert [r["distance_km"] for r in rows] == [0, None]


def test_gates_no_location_outside_and_global_review_order(client, db):
    first = add(db, "first")
    reviewed = add(db, "reviewed")
    inactive = add(db, "inactive", is_active=False)
    other = add(db, "other")
    other.category = "vet"
    for biz in [reviewed, inactive, other]:
        db.add(Review(business_id=biz.id, user_id=1, rating=5, is_public=True))
    db.add(Review(business_id=first.id, user_id=1, rating=5, is_public=False))
    db.commit()
    params = dict(category="café", limit=1)
    data = client.get("/api/businesses", params=params).json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == reviewed.id
    assert data["results"][0]["distance_km"] is None
    for coords in [dict(lat=0, lng=0), dict(lat=-30, lng=151)]:
        data = client.get("/api/businesses", params={**params, **coords}).json()
        assert data["count"] == 0 and data["results"] == []
    # A partial caller location still means no distance filter.
    assert client.get("/api/businesses", params={**params, "lat": 0}).json()["count"] == 1


def test_candidate_sql_budget_and_public_fields(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "0")
    for i in range(1101):
        add(db, f"candidate-{i}", phone="private-phone")
    db.commit()
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(models.engine, "before_cursor_execute", capture)
    try:
        for limit in [1, 50]:
            statements.clear()
            response = client.get("/api/businesses", params=dict(limit=limit))
            assert response.status_code == 200
            assert len(statements) == 4  # candidates + ceil(1101 / 500) stats
            assert response.json()["count"] == limit
            for row in response.json()["results"]:
                assert set(row) == {"id", "name", "category", "address", "lat", "lng",
                                    "review_count", "distance_km"}
    finally:
        event.remove(models.engine, "before_cursor_execute", capture)


def test_proximity_review_priority_and_id_ties(client, db):
    farther = add(db, "farther inserted first")
    farther.lat += 0.01
    coincident = add(db, "zero")
    tied = add(db, "zero tie")
    unknown = add(db, "missing longitude")
    unknown.lng = None
    reviewed = add(db, "reviewed farther")
    reviewed.lat += 0.02
    db.add(Review(business_id=reviewed.id, user_id=1, rating=1, is_public=True))
    db.commit()
    params = dict(lat=-33.89, lng=151.27, limit=50)
    rows = client.get("/api/businesses", params=params).json()["results"]
    assert [r["id"] for r in rows] == [reviewed.id, coincident.id, tied.id, farther.id, unknown.id]
    assert client.get("/api/businesses", params={**params, "limit": 1}).json()["results"] == rows[:1]


def test_forced_rank_boost_cannot_change_business_selection(client, db):
    from tests.conftest import sample_deal_payload, signed_post
    reviewed = add(db, "Reviewed")
    db.add(Review(business_id=reviewed.id, user_id=1, rating=1, is_public=True))
    db.commit()
    response = signed_post(client, "/api/ingest/hybridcard-deal", sample_deal_payload(
        business_name="Paid", discount_size=99, rank_boost=True))
    assert response.status_code == 200
    rows = client.get("/api/businesses", params=dict(category="café", limit=1)).json()["results"]
    assert [r["id"] for r in rows] == [reviewed.id]


def test_proximity_uses_unrounded_distance_before_limit(client, db):
    farther = add(db, "farther")
    farther.lat += 0.0002
    nearer = add(db, "nearer")
    nearer.lat += 0.0001
    db.commit()
    rows = client.get("/api/businesses", params=dict(lat=-33.89, lng=151.27)).json()["results"]
    assert [r["id"] for r in rows] == [nearer.id, farther.id]
    assert [r["distance_km"] for r in rows] == [0.0, 0.0]

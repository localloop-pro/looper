"""looper#107: GET /api/reviews/{business_id} tells "no such business" (404)
from "no reviews yet" (200 + []), and `limit` is bounded."""
import pytest

from models import Business, Review, User


def _business(db):
    biz = Business(name="Cafe Alpha", category="café", suburb="Bondi",
                   lat=-33.8908, lng=151.2748, source="manual")
    db.add(biz)
    db.commit()
    return biz


def test_unknown_business_is_404(client, db):
    resp = client.get("/api/reviews/999999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Business not found"
    assert resp.headers["cache-control"] == "no-store"


def test_known_business_without_reviews_is_200_empty(client, db):
    biz = _business(db)
    resp = client.get(f"/api/reviews/{biz.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["business_id"] == biz.id
    assert body["reviews"] == []
    assert body["total_reviews"] == 0
    assert body["avg_rating"] is None


def test_known_business_with_reviews_is_200(client, db):
    biz = _business(db)
    user = User(first_name="Tester", mobile_number="0400000001")
    db.add(user)
    db.flush()
    db.add(Review(business_id=biz.id, user_id=user.id, rating=4,
                  review_text="Great flat white, friendly staff"))
    db.commit()
    body = client.get(f"/api/reviews/{biz.id}").json()
    assert body["total_reviews"] == 1
    assert [r["rating"] for r in body["reviews"]] == [4]


@pytest.mark.parametrize("limit", [0, -1, 51, 100000])
def test_limit_out_of_range_is_422(client, db, limit):
    biz = _business(db)
    assert client.get(f"/api/reviews/{biz.id}?limit={limit}").status_code == 422


@pytest.mark.parametrize("limit", [1, 10, 50])
def test_limit_in_range_is_200(client, db, limit):
    biz = _business(db)
    assert client.get(f"/api/reviews/{biz.id}?limit={limit}").status_code == 200

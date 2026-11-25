"""POST /api/reviews: duplicate review from the same user (409) and the 1-5
rating bounds (422). Writes are locked by default, so each test opens them."""
import pytest

from models import Business, Review, User


def _setup(db):
    biz = Business(name="Cafe Alpha", category="café", suburb="Bondi",
                   lat=-33.8908, lng=151.2748, source="manual")
    user = User(first_name="Tester", mobile_number="0400000099")
    db.add_all([biz, user])
    db.commit()
    return biz, user


def _body(biz, user, rating=4):
    return {"business_id": biz.id, "user_id": user.id, "rating": rating,
            "review_text": "Great flat white"}


def test_first_review_is_accepted(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    biz, user = _setup(db)
    resp = client.post("/api/reviews", json=_body(biz, user))
    assert resp.status_code == 200
    assert resp.json()["business_review_count"] == 1


def test_duplicate_review_from_same_user_is_409(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    biz, user = _setup(db)
    assert client.post("/api/reviews", json=_body(biz, user, 5)).status_code == 200
    resp = client.post("/api/reviews", json=_body(biz, user, 1))
    assert resp.status_code == 409
    assert db.query(Review).count() == 1
    assert db.query(Review).one().rating == 5


@pytest.mark.parametrize("rating", [0, -1, 6, 100])
def test_rating_out_of_bounds_is_422(client, db, monkeypatch, rating):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    biz, user = _setup(db)
    assert client.post("/api/reviews", json=_body(biz, user, rating)).status_code == 422
    assert db.query(Review).count() == 0


@pytest.mark.parametrize("rating", [1, 5])
def test_rating_bounds_are_inclusive(client, db, monkeypatch, rating):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    biz, user = _setup(db)
    assert client.post("/api/reviews", json=_body(biz, user, rating)).status_code == 200

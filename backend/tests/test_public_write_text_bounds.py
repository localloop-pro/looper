"""Boundary tests for public write bounds on POST /api/reviews and /api/onboard (looper#175)."""

import pytest

from models import Business, Review, User


@pytest.fixture
def review_ctx(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    biz = Business(name="Cafe Bounds", category="café", suburb="Bondi",
                   lat=-33.89, lng=151.27)
    user = User(first_name="Tester", mobile_number="0400000175")
    db.add_all([biz, user])
    db.commit()
    return biz.id, user.id


def _review(biz_id, user_id, rating=5, text="x" * 10):
    return {"business_id": biz_id, "user_id": user_id, "rating": rating, "review_text": text}


@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_out_of_range_is_422(client, db, review_ctx, rating):
    biz_id, user_id = review_ctx
    assert client.post("/api/reviews", json=_review(biz_id, user_id, rating=rating)).status_code == 422
    assert db.query(Review).count() == 0


@pytest.mark.parametrize("length", [9, 2001])
def test_review_text_length_out_of_range_is_422(client, db, review_ctx, length):
    biz_id, user_id = review_ctx
    assert client.post("/api/reviews", json=_review(biz_id, user_id, text="x" * length)).status_code == 422
    assert db.query(Review).count() == 0


@pytest.mark.parametrize("rating,length", [(1, 10), (5, 2000)])
def test_review_accepts_values_at_the_limits(client, db, review_ctx, rating, length):
    biz_id, user_id = review_ctx
    response = client.post("/api/reviews", json=_review(biz_id, user_id, rating=rating, text="x" * length))
    assert response.status_code == 200, response.text


def _onboard(**over):
    body = {"first_name": "Sam", "mobile_number": "0400000176"}
    body.update(over)
    return body


@pytest.fixture
def writes_on(monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")


@pytest.mark.parametrize("over", [
    {"first_name": ""},
    {"first_name": "x" * 101},
    {"interest_category": "x" * 101},
    {"mobile_number": "040000017"},
    {"mobile_number": "04000001760"},
    {"mobile_number": "1400000176"},
    {"mobile_number": "+6140000017"},
    {"mobile_number": "+614000001760"},
    {"mobile_number": "+4400000176000"},
    {"mobile_number": "04000O0176"},
    {"mobile_number": "0400000176\n"},
])
def test_onboard_rejects_out_of_bounds_input(client, db, writes_on, over):
    assert client.post("/api/onboard", json=_onboard(**over)).status_code == 422
    assert db.query(User).count() == 0


@pytest.mark.parametrize("over", [
    {"first_name": "x"},
    {"first_name": "x" * 100},
    {"interest_category": "x" * 100},
    {"mobile_number": "+61400000176"},
])
def test_onboard_accepts_values_at_the_limits(client, db, writes_on, over):
    assert client.post("/api/onboard", json=_onboard(**over)).status_code == 200


@pytest.mark.parametrize("field,limit", [("title", 200), ("description", 2000), ("category", 100)])
def test_post_pin_rejects_text_one_over_the_limit(client, db, monkeypatch, field, limit):
    from models import MapPin
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number="0400000177")
    db.add(user)
    db.commit()
    body = {"user_id": user.id, "pin_type": "event", "title": "ok",
            "description": None, "lat": -33.89, "lng": 151.27, "category": None}
    body[field] = "x" * (limit + 1)
    assert client.post("/api/pins", json=body).status_code == 422
    assert db.query(MapPin).count() == 0

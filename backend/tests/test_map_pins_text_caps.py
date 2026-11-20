"""Regression for looper#170: public POST /api/pins caps title, description, category."""

import pytest

from models import MapPin, User


@pytest.mark.parametrize("field", ["title", "description", "category"])
def test_post_pin_rejects_oversized_text(client, db, monkeypatch, field):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number="0400000370")
    db.add(user)
    db.commit()
    body = {
        "user_id": user.id, "pin_type": "event", "title": "ok",
        "description": None, "lat": -33.89, "lng": 151.27, "category": None,
    }
    body[field] = "x" * 100_000

    response = client.post("/api/pins", json=body)

    assert response.status_code == 422, response.status_code
    assert db.query(MapPin).count() == 0


@pytest.mark.parametrize("field,limit", [("title", 200), ("description", 2000), ("category", 100)])
def test_post_pin_accepts_text_at_the_limit(client, db, monkeypatch, field, limit):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number="0400000371")
    db.add(user)
    db.commit()
    body = {
        "user_id": user.id, "pin_type": "event", "title": "ok",
        "description": None, "lat": -33.89, "lng": 151.27, "category": None,
    }
    body[field] = "x" * limit

    assert client.post("/api/pins", json=body).status_code == 200

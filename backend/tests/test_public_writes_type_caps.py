"""Regression for looper#174: public writes cap pin_type, user_type, preferred_language."""

import pytest

from models import MapPin, User


def _pin_body(user_id, pin_type="event"):
    return {
        "user_id": user_id, "pin_type": pin_type, "title": "ok",
        "description": None, "lat": -33.89, "lng": 151.27, "category": None,
    }


def test_post_pin_rejects_oversized_pin_type(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number="0400000374")
    db.add(user)
    db.commit()

    response = client.post("/api/pins", json=_pin_body(user.id, "x" * 100_000))

    assert response.status_code == 422, response.status_code
    assert db.query(MapPin).count() == 0


@pytest.mark.parametrize("field", ["user_type", "preferred_language"])
def test_onboard_rejects_oversized_field(client, db, monkeypatch, field):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    body = {"first_name": "Tester", "mobile_number": "0400000375", field: "x" * 100_000}

    response = client.post("/api/onboard", json=body)

    assert response.status_code == 422, response.status_code
    assert db.query(User).count() == 0


def test_post_pin_accepts_pin_type_at_the_limit(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number="0400000376")
    db.add(user)
    db.commit()

    assert client.post("/api/pins", json=_pin_body(user.id, "x" * 30)).status_code == 200


@pytest.mark.parametrize("field,limit", [("user_type", 20), ("preferred_language", 10)])
def test_onboard_accepts_field_at_the_limit(client, db, monkeypatch, field, limit):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    body = {"first_name": "Tester", "mobile_number": "0400000377", field: "x" * limit}

    assert client.post("/api/onboard", json=body).status_code == 200

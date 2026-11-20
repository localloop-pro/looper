"""Regression for looper#173: public POST /api/pins must reject an unknown user_id (404, like reviews)."""

from models import MapPin


def test_post_pin_unknown_user_returns_404_and_stores_nothing(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    body = {
        "user_id": 999999, "pin_type": "event", "title": "ghost",
        "description": None, "lat": -33.89, "lng": 151.27, "category": None,
    }

    response = client.post("/api/pins", json=body)

    assert response.status_code == 404, response.status_code
    assert db.query(MapPin).count() == 0


def test_post_pin_known_user_still_succeeds(client, db, monkeypatch):
    from models import User

    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number="0400000373")
    db.add(user)
    db.commit()
    body = {
        "user_id": user.id, "pin_type": "event", "title": "real",
        "description": None, "lat": -33.89, "lng": 151.27, "category": None,
    }

    assert client.post("/api/pins", json=body).status_code == 200
    assert db.query(MapPin).count() == 1

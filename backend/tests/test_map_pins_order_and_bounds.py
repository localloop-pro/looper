"""Regressions for looper#162 (follow-up to #160): pin cap order and write bounds."""

import pytest

from models import MapPin, User


def _user(db, mobile):
    user = User(first_name="Tester", mobile_number=mobile)
    db.add(user)
    db.flush()
    return user


def test_limit_keeps_the_nearer_pin_inside_one_rounding_step(client, db):
    # Both pins round to 0.0 km; the farther one is stored first.
    user = _user(db, "0400000311")
    db.add(MapPin(user_id=user.id, pin_type="offering", title="0.04 km", lat=0.00036, lng=0))
    db.add(MapPin(user_id=user.id, pin_type="offering", title="0.01 km", lat=0.00009, lng=0))
    db.commit()

    response = client.get("/api/pins", params={"lat": 0, "lng": 0, "radius_km": 1, "limit": 1})

    assert response.status_code == 200
    assert [pin["title"] for pin in response.json()["pins"]] == ["0.01 km"]


def test_newest_pins_are_returned_without_coordinates(client, db):
    user = _user(db, "0400000312")
    for i in range(105):
        db.add(MapPin(user_id=user.id, pin_type="event", title=f"pin{i}", lat=-33.89, lng=151.27))
        db.flush()
    db.commit()

    titles = [pin["title"] for pin in client.get("/api/pins").json()["pins"]]

    assert len(titles) == 100
    assert titles[0] == "pin104"
    assert "pin0" not in titles


@pytest.mark.parametrize("lat,lng", [(-33.89, 511.27), (-33.89, -180.01), (90.01, 151.27), (-91, 151.27)])
def test_post_pin_rejects_out_of_range_coordinates(client, db, monkeypatch, lat, lng):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = _user(db, "0400000313")
    db.commit()

    response = client.post("/api/pins", json={
        "user_id": user.id, "pin_type": "event", "title": "Out of range",
        "description": None, "lat": lat, "lng": lng, "category": None,
    })

    assert response.status_code == 422, response.text
    assert db.query(MapPin).count() == 0

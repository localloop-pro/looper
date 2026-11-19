"""Regression for issue #157: the public pin response must be bounded."""

from models import MapPin, User
from sqlalchemy import event
import models


def test_pin_response_respects_requested_limit_without_coordinates(client, db):
    user = User(first_name="Tester", mobile_number="0400000301")
    db.add(user)
    db.flush()
    db.add_all([
        MapPin(user_id=user.id, pin_type="offering", title=f"Pin {i}",
               lat=-33.89, lng=151.27)
        for i in range(3)
    ])
    db.commit()

    response = client.get("/api/pins", params={"limit": 2})

    assert response.status_code == 200
    assert response.json()["count"] == len(response.json()["pins"]) == 2


def test_radius_prefilter_and_nearest_limit(client, db):
    user = User(first_name="Tester", mobile_number="0400000302")
    db.add(user)
    db.flush()
    for title, lat, lng in [("far", 0.02, 0), ("near", 0, 0),
                            ("middle", 0.01, 0), ("outside", 1, 0)]:
        db.add(MapPin(user_id=user.id, pin_type="offering", title=title, lat=lat, lng=lng))
    db.commit()
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "FROM map_pins" in statement:
            statements.append(statement)

    event.listen(models.engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/pins", params={"lat": 0, "lng": 0, "radius_km": 5, "limit": 2})
    finally:
        event.remove(models.engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert [pin["title"] for pin in data["pins"]] == ["near", "middle"]
    assert data["pins"][0]["distance_km"] == 0.0
    assert statements and "map_pins.lat >=" in statements[0] and "map_pins.lng >=" in statements[0]
    all_nearby = client.get("/api/pins", params={"lat": 0, "lng": 0, "radius_km": 5}).json()
    assert {pin["title"] for pin in all_nearby["pins"]} == {"near", "middle", "far"}


def test_radius_crosses_antimeridian_and_rejects_box_corners(client, db):
    user = User(first_name="Tester", mobile_number="0400000303")
    db.add(user)
    db.flush()
    for title, lat, lng in [("across", 0, -179.99), ("corner", 0.08, 179.93)]:
        db.add(MapPin(user_id=user.id, pin_type="event", title=title, lat=lat, lng=lng))
    db.commit()
    response = client.get("/api/pins", params={"lat": 0, "lng": 179.99, "radius_km": 10})
    assert [pin["title"] for pin in response.json()["pins"]] == ["across"]


def test_limit_bounds(client):
    for limit in (0, 501):
        assert client.get("/api/pins", params={"limit": limit}).status_code == 422


def test_default_limit_and_polar_radius(client, db):
    user = User(first_name="Tester", mobile_number="0400000304")
    db.add(user)
    db.flush()
    db.add_all([MapPin(user_id=user.id, pin_type="event", title=f"Pin {i}",
                       lat=89.99, lng=180 if i == 0 else -180)
                for i in range(101)])
    db.commit()
    assert client.get("/api/pins").json()["count"] == 100
    response = client.get("/api/pins", params={"lat": 90, "lng": 0, "radius_km": 5, "limit": 101})
    assert response.json()["count"] == 101

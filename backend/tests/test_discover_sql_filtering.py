"""Reproduce #159: discovery should not load distant businesses into the ORM."""
from sqlalchemy import event
from sqlalchemy.orm import Session

from models import Business


def test_discover_does_not_load_distant_businesses(client, db, monkeypatch):
    monkeypatch.setenv("TYPEDB_ENABLED", "false")
    db.add_all([
        Business(name="Nearby", category="cafe", suburb="Bondi",
                 lat=-33.8915, lng=151.2743, is_active=True),
        *[Business(name=f"Distant {i}", category="cafe", suburb="Byron Bay",
                   lat=-28.65, lng=153.61, is_active=True) for i in range(20)],
    ])
    db.commit()
    loaded = []

    def record_business(_session, instance):
        if isinstance(instance, Business):
            loaded.append(instance.name)

    event.listen(Session, "loaded_as_persistent", record_business)
    try:
        response = client.get("/api/discover", params={"suburb": "Bondi", "radius_km": 5})
    finally:
        event.remove(Session, "loaded_as_persistent", record_business)

    assert response.status_code == 200
    assert [result["name"] for result in response.json()["results"]] == ["Nearby"]
    assert loaded == ["Nearby"], f"Loaded {len(loaded)} businesses, including distant rows: {loaded}"


def test_radius_boundary_preserves_proximity_order(client, db, monkeypatch):
    monkeypatch.setenv("TYPEDB_ENABLED", "false")
    db.add_all([
        Business(name="Inside", category="cafe", lat=0.0089, lng=0, is_active=True),
        Business(name="Near", category="cafe", lat=0.001, lng=0, is_active=True),
        Business(name="Outside", category="cafe", lat=0.0091, lng=0, is_active=True),
    ])
    db.commit()
    response = client.get("/api/discover", params={"lat": 0, "lng": 0, "radius_km": 1})
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["results"]] == ["Near", "Inside"]


def test_bounding_box_crosses_antimeridian(client, db, monkeypatch):
    monkeypatch.setenv("TYPEDB_ENABLED", "false")
    db.add(Business(name="Across", category="cafe", lat=0, lng=-179.99, is_active=True))
    db.commit()
    response = client.get("/api/discover", params={"lat": 0, "lng": 179.99, "radius_km": 5})
    assert [row["name"] for row in response.json()["results"]] == ["Across"]


def test_bounding_box_includes_all_longitudes_near_pole(client, db, monkeypatch):
    monkeypatch.setenv("TYPEDB_ENABLED", "false")
    db.add(Business(name="Polar", category="cafe", lat=89.99, lng=180, is_active=True))
    db.commit()
    response = client.get("/api/discover", params={"lat": 89.99, "lng": 0, "radius_km": 5})
    assert [row["name"] for row in response.json()["results"]] == ["Polar"]


def test_legacy_longitude_keeps_haversine_behavior(client, db, monkeypatch):
    monkeypatch.setenv("TYPEDB_ENABLED", "false")
    db.add(Business(name="Wrapped", category="cafe", lat=0, lng=360, is_active=True))
    db.commit()
    response = client.get("/api/discover", params={"lat": 0, "lng": 0, "radius_km": 1})
    assert [row["name"] for row in response.json()["results"]] == ["Wrapped"]

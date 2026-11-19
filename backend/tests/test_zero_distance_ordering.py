"""#134: a 0.0 km distance is a known distance, not a missing one.

A business or pin 0 to 50 m away rounds to 0.0 km. The old truthiness checks
(`if distance`) treated 0.0 as unknown: the output showed null and the sort
key fell back to 999, so a coincident result lost to a farther one with the
same relevance and review count. Both must treat 0.0 as a real distance.
"""
from models import Business, MapPin, Review, User

LAT, LNG = -33.8908, 151.2748  # Bondi Beach
NEAR_KM_DEG = 0.009  # about 1 km of latitude


def _vet(db, name, lat):
    biz = Business(name=name, category="vet", suburb="Eastern Suburbs",
                   lat=lat, lng=LNG, source="manual", is_active=True)
    db.add(biz)
    db.flush()
    user = User(first_name="Tester", mobile_number=f"04000002{biz.id:02d}")
    db.add(user)
    db.flush()
    db.add(Review(business_id=biz.id, user_id=user.id, rating=4,
                  review_text="Kind staff, gentle with pets."))
    db.commit()
    return biz


def test_search_coincident_business_is_zero_km_and_ranks_first(client, db):
    # Far one is created first so it wins any tie-break by id.
    far = _vet(db, "Far Vet", LAT + NEAR_KM_DEG)
    here = _vet(db, "Here Vet", LAT)

    resp = client.get("/api/search", params={
        "q": "vet", "lat": LAT, "lng": LNG, "radius_km": 5.0,
    })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["name"] for r in results] == ["Here Vet", "Far Vet"]
    assert results[0]["distance_km"] == 0.0
    assert results[1]["distance_km"] is not None and results[1]["distance_km"] > 0
    assert here.id > far.id  # the order above is proximity, not insertion


def test_map_pins_coincident_pin_is_zero_km_and_sorts_first(client, db):
    user = User(first_name="Tester", mobile_number="0400000301")
    db.add(user)
    db.flush()
    db.add(MapPin(user_id=user.id, pin_type="offering", title="Far pin",
                  lat=LAT + NEAR_KM_DEG, lng=LNG))
    db.add(MapPin(user_id=user.id, pin_type="offering", title="Here pin",
                  lat=LAT, lng=LNG))
    db.commit()

    resp = client.get("/api/pins", params={"lat": LAT, "lng": LNG, "radius_km": 5.0})
    assert resp.status_code == 200
    pins = resp.json()["pins"]
    assert [p["title"] for p in pins] == ["Here pin", "Far pin"]
    assert pins[0]["distance_km"] == 0.0

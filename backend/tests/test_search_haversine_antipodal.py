"""looper#123: Clamp haversine rounding to prevent ValueError on antipodal searches.

Floating-point rounding for valid antipodal or near-antipodal coordinates can
yield intermediate value a > 1.0, causing ValueError in sqrt(1 - a). The fix
clamps a to [0, 1] before computing square roots.

After PR#122 (/businesses now scans all candidates before result limit), even
an off-page antipodal candidate outside the requested radius can trigger the
500 error. This test ensures valid antipodal/near-antipodal and coincident
coordinates return 200 with finite distances and correct ordering.
"""
import pytest
import math

import routes.search
from models import Business, Review, User


LAT, LNG = -33.8908, 151.2748  # Bondi Beach


def _biz(db, name, lat, lng=LNG, *, category="vet", reviews=0):
    """Helper to create a business with optional reviews."""
    b = Business(name=name, category=category, suburb="Eastern Suburbs",
                 lat=lat, lng=lng, source="manual", is_active=True)
    db.add(b)
    db.flush()
    if reviews:
        user = User(first_name="Tester", mobile_number=f"04000001{b.id:02d}")
        db.add(user)
        db.flush()
        for i in range(reviews):
            db.add(Review(business_id=b.id, user_id=user.id, rating=4,
                          review_text=f"Kind staff, visit {i + 1}."))
    db.commit()
    return b


def test_search_with_antipodal_candidate_returns_200(client, db):
    """Antipodal candidate outside radius should not trigger ValueError.

    Before fix: antipodal candidate (outside page) triggers haversine ValueError.
    After fix: /search returns 200 with only nearby match (antipodal filtered out).
    """
    # Nearby match inside radius
    _biz(db, "Local Vet", LAT - 0.01, reviews=2)

    # Antipodal candidate (exactly opposite side of Earth)
    antipodal_lat = -LAT
    antipodal_lng = LNG + 180 if LNG < 0 else LNG - 180
    _biz(db, "Antipodal Vet", antipodal_lat, antipodal_lng, reviews=1)

    # Request succeeds: no ValueError from antipodal calculation
    resp = client.get("/api/search", params={
        "q": "vet",
        "lat": LAT,
        "lng": LNG,
        "radius_km": 5.0,
        "limit": 20,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Local Vet"
    assert data["results"][0]["distance_km"] is not None
    assert math.isfinite(data["results"][0]["distance_km"])


def test_businesses_endpoint_with_antipodal_candidate_returns_200(client, db):
    """_/businesses_ endpoint with antipodal candidate outside radius returns 200."""
    # Eligible in_range
    _biz(db, "Close Vet", LAT - 0.01)

    # Antipodal outside_range
    _biz(db, "Far Antipodal", -LAT, LNG + 180)

    resp = client.get("/api/businesses", params={
        "lat": LAT,
        "lng": LNG,
        "radius_km": 5.0,
        "limit": 20,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Close Vet"
    assert math.isfinite(data["results"][0]["distance_km"])


def test_haversine_direct_antipodal_calls_return_finite():
    """Direct unit tests for haversine with antipodal coordinates."""
    # Antipodal points should have ~maximum distance (no ValueError)
    dist = routes.search.haversine_km(0, 0, 0, 180)
    assert 19900 < dist < 20200  # ~20015 km (half Earth's circumference)
    assert math.isfinite(dist)

    # Same point returns 0
    dist = routes.search.haversine_km(51.5, -0.1, 51.5, -0.1)
    assert dist == 0.0

    # Very close points
    dist = routes.search.haversine_km(51.5, -0.1, 51.50001, -0.10001)
    assert 0 <= dist < 0.1
    assert math.isfinite(dist)


def test_haversine_sydney_london_distance():
    """Real-world coordinates (Sydney to London) remain accurate."""
    dist = routes.search.haversine_km(-33.8688, 151.2093, 51.5074, -0.1278)
    assert 16900 < dist < 17100
    assert math.isfinite(dist)


def test_haversine_sydney_near_london_antipode():
    """Sydney to near-antipode of London (near New Zealand)."""
    dist = routes.search.haversine_km(-33.8688, 151.2093, -51.5074, 179.8722)
    assert 2000 < dist < 4000
    assert math.isfinite(dist)


@pytest.mark.parametrize("lat1,lng1,lat2,lng2", [
    (0, 0, 0, 180),           # Exact antipode across equator
    (89, 0, -89, 180),        # Poles
    (-33.8688, 151.2093, 33.8688, -28.7907),  # Sydney antipode
    (45, 45, -45, -135),      # Mid-latitude antipode
])
def test_haversine_all_antipodal_pairs_finite(lat1, lng1, lat2, lng2):
    """All antipodal coordinate pairs return finite distances (not ValueError)."""
    dist = routes.search.haversine_km(lat1, lng1, lat2, lng2)
    assert math.isfinite(dist), f"Antipodal ({lat1},{lng1}) to ({lat2},{lng2}) returned {dist}"
    assert dist > 0


def test_search_results_with_diverse_nearby_distances(client, db):
    """Results ordered by relevance, review count, then distance (diverse distances)."""
    # Same location, different review counts
    _biz(db, "Popular Vet", LAT, LNG, reviews=3)
    _biz(db, "New Vet", LAT + 0.01, LNG, reviews=1)  # ~1.1 km away

    resp = client.get("/api/search", params={
        "q": "vet",
        "lat": LAT,
        "lng": LNG,
        "radius_km": 100.0,
        "limit": 20,
    })
    assert resp.status_code == 200
    data = resp.json()
    names = [r["name"] for r in data["results"]]
    # At same relevance, more reviews rank first (Popular has 3, New has 1)
    assert names == ["Popular Vet", "New Vet"]

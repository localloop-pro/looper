"""looper#95: bad coordinates on public read endpoints are a 422, not a 500.

``GET /api/search?q=vet&lat=inf&lng=1`` used to reach ``haversine_km`` and
crash with a 500, and ``lat=999`` was accepted silently. Every public read
endpoint now takes ``Latitude`` / ``Longitude`` from ``routes.params``:
finite only (``allow_inf_nan=False``), -90..90 and -180..180. FastAPI turns
a bad value into its normal 422 before the route body runs.
"""
import pytest

from models import Business, MapPin, User

# Bondi Beach.
LAT, LNG = -33.8908, 151.2748

# (path, the other query params each endpoint needs)
ENDPOINTS = [
    ("/api/search", {"q": "vet"}),
    ("/api/businesses", {}),
    ("/api/discover", {}),
    ("/api/pins", {}),
    ("/api/tourist-info", {}),
]

NON_FINITE = ["inf", "-inf", "nan", "NaN", "Infinity", "1e309", "-1e309"]
BAD_LAT = NON_FINITE + ["91", "-91", "999"]
BAD_LNG = NON_FINITE + ["181", "-181"]


def _assert_clean_422(resp, field):
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "Traceback" not in resp.text
    assert any(err["loc"] == ["query", field] for err in body["detail"]), body


@pytest.mark.parametrize("path,extra", ENDPOINTS, ids=[p for p, _ in ENDPOINTS])
@pytest.mark.parametrize("bad", BAD_LAT)
def test_bad_latitude_is_422(client, path, extra, bad):
    resp = client.get(path, params={**extra, "lat": bad, "lng": LNG})
    _assert_clean_422(resp, "lat")


@pytest.mark.parametrize("path,extra", ENDPOINTS, ids=[p for p, _ in ENDPOINTS])
@pytest.mark.parametrize("bad", BAD_LNG)
def test_bad_longitude_is_422(client, path, extra, bad):
    resp = client.get(path, params={**extra, "lat": LAT, "lng": bad})
    _assert_clean_422(resp, "lng")


def test_issue_repro_search_inf_is_422_not_500(client):
    resp = client.get("/api/search", params={"q": "vet", "lat": "inf", "lng": "1"})
    _assert_clean_422(resp, "lat")


@pytest.mark.parametrize("path", ["/api/businesses", "/api/pins"])
@pytest.mark.parametrize("bad", ["0", "-1", "5000.01", "inf", "nan", "1e309"])
def test_bad_radius_is_422(client, path, bad):
    resp = client.get(path, params={"lat": LAT, "lng": LNG, "radius_km": bad})
    _assert_clean_422(resp, "radius_km")


@pytest.mark.parametrize("bad", ["0", "-5"])
def test_businesses_limit_below_one_is_422(client, bad):
    resp = client.get("/api/businesses", params={"limit": bad})
    _assert_clean_422(resp, "limit")


@pytest.mark.parametrize("path,extra", ENDPOINTS, ids=[p for p, _ in ENDPOINTS])
@pytest.mark.parametrize("lat,lng", [(LAT, LNG), (90, 180), (-90, -180), (0, 0)])
def test_valid_coordinates_still_200(client, path, extra, lat, lng):
    resp = client.get(path, params={**extra, "lat": lat, "lng": lng})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("path", ["/api/businesses", "/api/pins"])
@pytest.mark.parametrize("radius", ["0.01", "5000"])
def test_radius_edges_still_200(client, path, radius):
    resp = client.get(path, params={"lat": LAT, "lng": LNG, "radius_km": radius})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("path,extra", [
    ("/api/search", {"q": "vet"}),
    ("/api/businesses", {}),
    ("/api/discover", {"suburb": "Bondi"}),
    ("/api/pins", {}),
])
def test_optional_coordinates_still_optional(client, path, extra):
    resp = client.get(path, params=extra)
    assert resp.status_code == 200, resp.text


def test_tourist_info_still_requires_coordinates(client):
    resp = client.get("/api/tourist-info")
    assert resp.status_code == 422


def test_bondi_results_and_order_unchanged(client, db):
    """Valid Bondi coordinates: same rows, same order, same distances."""
    for name, dlat in [("Near Vet", 0.001), ("Mid Vet", 0.01), ("Far Vet", 0.03)]:
        db.add(Business(name=name, category="vet", suburb="Bondi",
                        lat=LAT + dlat, lng=LNG, source="manual", is_active=True))
    user = User(first_name="Tester", mobile_number="0400000195")
    db.add(user)
    db.flush()
    db.add(MapPin(user_id=user.id, pin_type="event", title="Beach clean",
                  lat=LAT + 0.002, lng=LNG))
    db.commit()

    search = client.get("/api/search", params={"q": "vet", "lat": LAT, "lng": LNG,
                                               "radius_km": 5}).json()
    assert [r["name"] for r in search["results"]] == ["Near Vet", "Mid Vet", "Far Vet"]

    biz = client.get("/api/businesses", params={"lat": LAT, "lng": LNG,
                                                "radius_km": 5}).json()
    assert [r["name"] for r in biz["results"]] == ["Near Vet", "Mid Vet", "Far Vet"]

    pins = client.get("/api/pins", params={"lat": LAT, "lng": LNG}).json()
    assert [p["title"] for p in pins["pins"]] == ["Beach clean"]

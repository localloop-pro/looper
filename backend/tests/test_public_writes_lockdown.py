"""BLIND-SPOTS §3.6 / step 7 (looper#27): public writes behind a kill switch,
profile reads deleted, verified_visit never taken from the caller."""
import pytest

from models import Business, MapPin, Review, User

WRITE_PATHS = ["/api/reviews", "/api/onboard", "/api/pins"]


@pytest.fixture()
def writes_off(monkeypatch):
    monkeypatch.delenv("LOOPER_PUBLIC_WRITES", raising=False)


@pytest.fixture()
def writes_on(monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")


def _business(db):
    biz = Business(name="Cafe Alpha", category="café", suburb="Bondi",
                   lat=-33.8908, lng=151.2748, source="manual")
    db.add(biz)
    db.commit()
    return biz


def _user(db, mobile="0400000001"):
    user = User(first_name="Tester", mobile_number=mobile, join_code="246810")
    db.add(user)
    db.commit()
    return user


# --- flag unset: writes closed ------------------------------------------------

@pytest.mark.parametrize("path", WRITE_PATHS)
def test_empty_body_write_is_403_not_422(client, db, writes_off, path):
    resp = client.post(path, json={})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "public writes are disabled"}


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_no_body_at_all_is_403(client, db, writes_off, path):
    assert client.post(path).status_code == 403


@pytest.mark.parametrize("value", ["", "1", "yes", "True", "TRUE", " true", "false"])
def test_only_exact_true_opens_writes(client, db, monkeypatch, value):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", value)
    assert client.post("/api/pins", json={}).status_code == 403


def test_valid_bodies_write_nothing_when_closed(client, db, writes_off):
    biz = _business(db)
    user = _user(db)
    client.post("/api/reviews", json={"business_id": biz.id, "user_id": user.id, "rating": 5,
                                      "review_text": "Lovely coffee and staff"})
    client.post("/api/onboard", json={"first_name": "Ann", "mobile_number": "0400000002"})
    client.post("/api/pins", json={"user_id": user.id, "pin_type": "offering", "title": "x",
                                   "description": None, "lat": -33.89, "lng": 151.27,
                                   "category": None})
    db.expire_all()
    assert db.query(Review).count() == 0
    assert db.query(User).count() == 1
    assert db.query(MapPin).count() == 0


@pytest.mark.parametrize("path", ["/api/users/1", "/api/code/123456"])
def test_profile_reads_are_gone(client, db, writes_off, path):
    _user(db)
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/api/users/1", "/api/code/246810"])
def test_profile_reads_stay_gone_when_writes_open(client, db, writes_on, path):
    _user(db)
    resp = client.get(path)
    assert resp.status_code == 404
    assert "246810" not in resp.text


def test_public_reads_stay_open(client, db, writes_off):
    biz = _business(db)
    assert client.get(f"/api/reviews/{biz.id}").status_code == 200
    assert client.get("/api/pins").status_code == 200
    assert client.get("/api/pins", params={"lat": -33.8908, "lng": 151.2748,
                                           "radius_km": 5}).status_code == 200
    assert client.get("/api/tourist-info", params={"lat": -33.8908,
                                                   "lng": 151.2748}).status_code == 200


# --- flag on: writes work, but stay honest -------------------------------------

def test_review_ignores_caller_verified_visit(client, db, writes_on):
    biz = _business(db)
    user = _user(db)
    resp = client.post("/api/reviews", json={
        "business_id": biz.id, "user_id": user.id, "rating": 5,
        "review_text": "Lovely coffee and staff", "verified_visit": True})
    assert resp.status_code == 200
    review = db.query(Review).one()
    assert review.verified_visit is False
    public = client.get(f"/api/reviews/{biz.id}").json()["reviews"]
    assert [r["verified_visit"] for r in public] == [False]


def test_onboard_new_number_works(client, db, writes_on):
    resp = client.post("/api/onboard", json={"first_name": "Ann", "mobile_number": "0400000002"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Ann" and len(body["join_code"]) == 6


def test_onboard_existing_number_echoes_nothing(client, db, writes_on):
    existing = _user(db, mobile="0400000003")
    resp = client.post("/api/onboard", json={"first_name": "Mallory",
                                             "mobile_number": "0400000003"})
    assert resp.status_code == 409
    assert resp.json() == {"detail": "could not complete sign-up"}
    assert existing.join_code not in resp.text
    assert "Tester" not in resp.text
    db.expire_all()
    assert db.query(User).count() == 1


def test_pin_write_works(client, db, writes_on):
    user = _user(db)
    resp = client.post("/api/pins", json={
        "user_id": user.id, "pin_type": "offering", "title": "Free surfboard",
        "description": "Pick up today", "lat": -33.89, "lng": 151.27, "category": "sport"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Free surfboard"
    assert client.get("/api/pins").json()["count"] == 1

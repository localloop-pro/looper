"""Regression for looper#169: POST /api/pins must answer 422, not 500, for out-of-range expires_in_days."""

from datetime import datetime, timedelta, timezone

import pytest

from models import MapPin, User


def _post(client, db, monkeypatch, mobile, **extra):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    user = User(first_name="Tester", mobile_number=mobile)
    db.add(user)
    db.commit()
    body = {"user_id": user.id, "pin_type": "event", "title": "Expiry",
            "description": None, "lat": -33.89, "lng": 151.27, "category": None}
    body.update(extra)
    return client.post("/api/pins", json=body)


@pytest.mark.parametrize("days", [10**9, 3_000_000, 366, -1])
def test_post_pin_rejects_out_of_range_expiry(client, db, monkeypatch, days):
    assert _post(client, db, monkeypatch, "0400000169", expires_in_days=days).status_code == 422


def test_post_pin_accepts_maximum_expiry(client, db, monkeypatch):
    response = _post(client, db, monkeypatch, "0400000170", expires_in_days=365)
    assert response.status_code == 200
    expires = db.query(MapPin).one().expires_at.replace(tzinfo=timezone.utc)
    assert abs(expires - (datetime.now(timezone.utc) + timedelta(days=365))) < timedelta(minutes=1)


def test_post_pin_zero_means_no_expiry_and_default_is_30(client, db, monkeypatch):
    assert _post(client, db, monkeypatch, "0400000171", expires_in_days=0).status_code == 200
    assert _post(client, db, monkeypatch, "0400000172").status_code == 200
    zero, default = db.query(MapPin).order_by(MapPin.id).all()
    assert zero.expires_at is None
    expires = default.expires_at.replace(tzinfo=timezone.utc)
    assert abs(expires - (datetime.now(timezone.utc) + timedelta(days=30))) < timedelta(minutes=1)

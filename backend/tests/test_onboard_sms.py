"""Twilio join-code SMS after onboard — mocked, no real network (looper#158)."""

import logging
from datetime import datetime, timedelta, timezone

import pytest

from models import OnboardSmsSend, User
from services import onboard_sms


@pytest.fixture(autouse=True)
def clear_sms_rate_limiter():
    onboard_sms.rate_limiter.clear()
    yield
    onboard_sms.rate_limiter.clear()


@pytest.fixture
def writes_on(monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")


@pytest.fixture
def twilio_env(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test_sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_auth_token")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550001111")


def _onboard(client, mobile="0400000999", first_name="Sam"):
    return client.post(
        "/api/onboard",
        json={"first_name": first_name, "mobile_number": mobile},
    )


def test_new_onboard_sends_sms_when_twilio_configured(client, db, writes_on, twilio_env, monkeypatch):
    calls = []

    def capture(cfg, to_e164, join_code, client=None):
        calls.append((to_e164, join_code))

    monkeypatch.setattr(onboard_sms, "send_join_code_via_twilio", capture)

    resp = _onboard(client)
    assert resp.status_code == 200
    body = resp.json()
    assert list(body.keys()) == ["message"]
    assert "join_code" not in body and "user_id" not in body

    user = db.query(User).filter(User.mobile_number == "0400000999").one()
    assert len(user.join_code) == 6
    assert calls == [("+61400000999", user.join_code)]


def test_onboard_without_twilio_creds_skips_sms(client, db, writes_on, monkeypatch, caplog):
    for name in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_API_KEY_SID",
        "TWILIO_API_KEY_SECRET",
        "TWILIO_FROM_NUMBER",
        "TWILIO_MESSAGING_SERVICE_SID",
    ):
        monkeypatch.delenv(name, raising=False)

    sent = []
    monkeypatch.setattr(
        onboard_sms,
        "send_join_code_via_twilio",
        lambda *a, **k: sent.append(True),
    )

    caplog.set_level(logging.WARNING, logger="looper.onboard_sms")
    resp = _onboard(client, mobile="0400000998")
    assert resp.status_code == 200
    assert resp.json()["message"]
    assert not sent

    user = db.query(User).one()
    log_text = " ".join(r.getMessage() for r in caplog.records)
    assert user.join_code not in log_text
    assert "0400000998" not in log_text
    assert user.mobile_number not in log_text


def test_http_body_never_contains_join_code(client, db, writes_on, twilio_env, monkeypatch):
    monkeypatch.setattr(onboard_sms, "send_join_code_via_twilio", lambda *a, **k: None)
    resp = _onboard(client, mobile="0400000997")
    assert resp.status_code == 200
    raw = resp.text
    user = db.query(User).one()
    assert user.join_code not in raw


def test_existing_mobile_rate_limited_resend_same_ack(client, db, writes_on, twilio_env, monkeypatch):
    """Existing numbers: re-send stored code when rate limit allows; HTTP stays identical."""
    sent_codes = []
    monkeypatch.setattr(
        onboard_sms,
        "send_join_code_via_twilio",
        lambda _cfg, _to, code, client=None: sent_codes.append(code),
    )

    db.add(User(first_name="Tester", mobile_number="0400000996", join_code="654321"))
    db.commit()

    first = _onboard(client, mobile="0400000996", first_name="Other")
    second = _onboard(client, mobile="0400000996", first_name="Other")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert db.query(User).filter(User.mobile_number == "0400000996").count() == 1
    assert sent_codes == ["654321", "654321"]


def test_daily_cap_skips_send_same_http_ack(client, db, writes_on, twilio_env, monkeypatch, caplog):
    monkeypatch.setenv("LOOPER_SMS_DAILY_CAP", "1")
    calls = []
    monkeypatch.setattr(
        onboard_sms,
        "send_join_code_via_twilio",
        lambda *a, **k: calls.append(True),
    )

    caplog.set_level(logging.WARNING, logger="looper.onboard_sms")
    first = _onboard(client, mobile="0400000881")
    second = _onboard(client, mobile="0400000882")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1
    daily_logs = [r for r in caplog.records if "daily cap" in r.getMessage()]
    assert daily_logs
    log_text = " ".join(r.getMessage() for r in caplog.records)
    assert "0400000882" not in log_text and "join" not in log_text.lower()


def test_per_number_limit_survives_limiter_reinstantiation(db):
    """SQLite ledger enforces cap across new limiter instances (worker restart)."""
    mobile = "0400000777"
    first = onboard_sms.OnboardSmsRateLimiter()
    second = onboard_sms.OnboardSmsRateLimiter()

    for _ in range(onboard_sms.ONBOARD_SMS_LIMIT_PER_HOUR):
        assert first.allow(mobile)

    assert not second.allow(mobile)


def test_rolling_hour_window_not_clock_aligned(db, monkeypatch):
    """A send just outside the 60-minute window does not count toward the cap."""
    monkeypatch.setenv("LOOPER_SMS_DAILY_CAP", "100")
    mobile = "0400000666"
    key = onboard_sms.hashed_mobile_key(mobile)
    old = datetime.now(timezone.utc) - timedelta(hours=1, minutes=5)
    db.add(OnboardSmsSend(mobile_key=key, sent_at=old))
    for _ in range(onboard_sms.ONBOARD_SMS_LIMIT_PER_HOUR - 1):
        db.add(
            OnboardSmsSend(
                mobile_key=key,
                sent_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            )
        )
    db.commit()

    limiter = onboard_sms.OnboardSmsRateLimiter()
    assert limiter.allow(mobile)
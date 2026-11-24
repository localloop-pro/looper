"""Join-code delivery by SMS after POST /api/onboard (looper#158).

Runs in a FastAPI BackgroundTasks worker so HTTP ack timing stays uniform.
Never logs mobiles or join codes.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import httpx

from models import OnboardSmsSend, SessionLocal, User

LOGGER = logging.getLogger("looper.onboard_sms")

# Per hashed-mobile cap; rolling 60-minute window (not clock-aligned).
ONBOARD_SMS_LIMIT_PER_HOUR = 3
DEFAULT_SMS_DAILY_CAP = 200
MOBILE_KEY_SALT_DEFAULT = "looper-onboard-sms-v1"

SkipReason = Literal["daily_cap", "rate_limit"]


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: str
    auth_username: str
    auth_password: str
    from_number: Optional[str]
    messaging_service_sid: Optional[str]


def _rate_salt() -> str:
    return (os.environ.get("LOOPER_SMS_RATE_SALT") or MOBILE_KEY_SALT_DEFAULT).strip()


def hashed_mobile_key(mobile: str) -> str:
    """SHA-256 of salt + mobile — stored in SQLite, not the raw number."""
    payload = f"{_rate_salt()}:{mobile}".encode()
    return hashlib.sha256(payload).hexdigest()


def sms_daily_cap_from_env() -> int:
    raw = (os.environ.get("LOOPER_SMS_DAILY_CAP") or "").strip()
    if not raw:
        return DEFAULT_SMS_DAILY_CAP
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_SMS_DAILY_CAP


def _utc_day_start(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


class OnboardSmsRateLimiter:
    """Rolling one-hour window per hashed mobile; counts durable in SQLite."""

    def clear(self) -> None:
        session = SessionLocal()
        try:
            session.query(OnboardSmsSend).delete()
            session.commit()
        finally:
            session.close()

    def allow(self, mobile: str, limit: int = ONBOARD_SMS_LIMIT_PER_HOUR) -> bool:
        ok, _reason = self.try_record(mobile, limit=limit)
        return ok

    def try_record(
        self, mobile: str, limit: int = ONBOARD_SMS_LIMIT_PER_HOUR,
    ) -> tuple[bool, Optional[SkipReason]]:
        now = datetime.now(timezone.utc)
        cap = sms_daily_cap_from_env()
        if cap <= 0:
            return False, "daily_cap"

        day_start = _utc_day_start(now)
        window_start = now - timedelta(hours=1)
        key = hashed_mobile_key(mobile)

        session = SessionLocal()
        try:
            daily_count = (
                session.query(OnboardSmsSend)
                .filter(OnboardSmsSend.sent_at >= day_start)
                .count()
            )
            if daily_count >= cap:
                return False, "daily_cap"

            hourly_count = (
                session.query(OnboardSmsSend)
                .filter(
                    OnboardSmsSend.mobile_key == key,
                    OnboardSmsSend.sent_at >= window_start,
                )
                .count()
            )
            if hourly_count >= limit:
                return False, "rate_limit"

            session.add(OnboardSmsSend(mobile_key=key, sent_at=now))
            session.commit()
            return True, None
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


rate_limiter = OnboardSmsRateLimiter()


def twilio_config_from_env() -> Optional[TwilioConfig]:
    account_sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    if not account_sid:
        return None

    api_key_sid = (os.environ.get("TWILIO_API_KEY_SID") or "").strip()
    api_key_secret = (os.environ.get("TWILIO_API_KEY_SECRET") or "").strip()
    auth_token = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()

    if api_key_sid and api_key_secret:
        auth_username, auth_password = api_key_sid, api_key_secret
    elif auth_token:
        auth_username, auth_password = account_sid, auth_token
    else:
        return None

    from_number = (os.environ.get("TWILIO_FROM_NUMBER") or "").strip() or None
    messaging_service_sid = (
        os.environ.get("TWILIO_MESSAGING_SERVICE_SID") or ""
    ).strip() or None
    if not from_number and not messaging_service_sid:
        return None

    return TwilioConfig(
        account_sid=account_sid,
        auth_username=auth_username,
        auth_password=auth_password,
        from_number=from_number,
        messaging_service_sid=messaging_service_sid,
    )


def mobile_to_e164(mobile: str) -> str:
    if mobile.startswith("+61"):
        return mobile
    if mobile.startswith("0") and len(mobile) == 10:
        return "+61" + mobile[1:]
    return mobile


def _sms_body(join_code: str) -> str:
    return f"Your Bondi Local Loop join code is {join_code}."


def send_join_code_via_twilio(
    cfg: TwilioConfig, to_e164: str, join_code: str, client: Optional[httpx.Client] = None,
) -> None:
    """POST to Twilio Messaging REST API (injected client for tests)."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg.account_sid}/Messages.json"
    data: dict[str, str] = {"To": to_e164, "Body": _sms_body(join_code)}
    if cfg.messaging_service_sid:
        data["MessagingServiceSid"] = cfg.messaging_service_sid
    else:
        data["From"] = cfg.from_number or ""

    owns_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        resp = http.post(url, data=data, auth=(cfg.auth_username, cfg.auth_password))
        if resp.status_code >= 400:
            LOGGER.warning(
                "onboard SMS send failed (Twilio HTTP %s)", resp.status_code,
            )
    except httpx.HTTPError:
        LOGGER.warning("onboard SMS send failed (network error)")
    finally:
        if owns_client:
            http.close()


def deliver_join_code_sms(mobile_number: str) -> None:
    """Background worker: send stored join code when configured and allowed."""
    cfg = twilio_config_from_env()
    if cfg is None:
        LOGGER.warning("onboard SMS skipped: Twilio not configured")
        return

    ok, reason = rate_limiter.try_record(mobile_number)
    if not ok:
        if reason == "daily_cap":
            LOGGER.warning("onboard SMS skipped: daily cap")
        else:
            LOGGER.warning("onboard SMS skipped: rate limit")
        return

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.mobile_number == mobile_number).first()
        if user is None:
            return
        send_join_code_via_twilio(cfg, mobile_to_e164(mobile_number), user.join_code)
    finally:
        session.close()
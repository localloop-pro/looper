"""Join-code delivery by SMS after POST /api/onboard (looper#158).

Runs in a FastAPI BackgroundTasks worker so HTTP ack timing stays uniform.
Never logs mobiles or join codes.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import httpx

from models import SessionLocal, User

LOGGER = logging.getLogger("looper.onboard_sms")

# Per-mobile cap; applies to new sign-ups and existing re-sends alike.
ONBOARD_SMS_LIMIT_PER_HOUR = 3


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: str
    auth_username: str
    auth_password: str
    from_number: Optional[str]
    messaging_service_sid: Optional[str]


class OnboardSmsRateLimiter:
    """Fixed one-hour window per hashed mobile key."""

    MAX_KEYS = 10_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: OrderedDict[str, tuple[int, int]] = OrderedDict()

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()

    def allow(self, mobile: str, limit: int = ONBOARD_SMS_LIMIT_PER_HOUR) -> bool:
        now = time.time()
        window = int(now // 3600)
        key = f"sms:{mobile}"
        with self._lock:
            seen_window, count = self._windows.get(key, (window, 0))
            if seen_window != window:
                count = 0
            count += 1
            self._windows[key] = (window, count)
            self._windows.move_to_end(key)
            while len(self._windows) > self.MAX_KEYS:
                self._windows.popitem(last=False)
        return count <= limit


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

    if not rate_limiter.allow(mobile_number):
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
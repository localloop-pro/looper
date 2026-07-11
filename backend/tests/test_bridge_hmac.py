"""Unit tests for services/bridge_hmac.py — verify/sign round-trip + edges."""
import re

import pytest

from services import bridge_hmac
from services.bridge_hmac import BridgeAuthError, REPLAY_WINDOW_MS

SECRET = "unit-secret"
KEYS = {"hc-1": SECRET, "hc-2": SECRET}
BODY = b'{"hello":"world"}'
NOW = 1_750_000_000_000  # fixed clock for deterministic window tests


def signed_headers(ts=NOW, secret=SECRET, key_id="hc-1"):
    return {k.lower(): v for k, v in bridge_hmac.sign(BODY, secret, key_id, ts).items()}


def test_sign_header_shapes():
    headers = bridge_hmac.sign(BODY, SECRET, "hc-1", NOW)
    assert re.fullmatch(r"sha256=[0-9a-f]{64}", headers["X-HC-Signature"])
    assert headers["X-HC-Key-Id"] == "hc-1"
    assert headers["X-HC-Timestamp"] == str(NOW)  # ms, as string


def test_round_trip():
    assert bridge_hmac.verify(BODY, signed_headers(), keys=KEYS, now_ms=NOW) == "hc-1"


def test_multi_key_lookup():
    headers = signed_headers(key_id="hc-2")
    assert bridge_hmac.verify(BODY, headers, keys=KEYS, now_ms=NOW) == "hc-2"


def test_unknown_key_id():
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, signed_headers(key_id="hc-9"), keys=KEYS, now_ms=NOW)


def test_wrong_secret():
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, signed_headers(secret="other"), keys=KEYS, now_ms=NOW)


def test_tampered_body():
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY + b" ", signed_headers(), keys=KEYS, now_ms=NOW)


def test_window_edges():
    # exactly at the window boundary passes; one ms past fails
    for delta in (REPLAY_WINDOW_MS, -REPLAY_WINDOW_MS):
        headers = signed_headers(ts=NOW + delta)
        assert bridge_hmac.verify(BODY, headers, keys=KEYS, now_ms=NOW) == "hc-1"
    for delta in (REPLAY_WINDOW_MS + 1, -(REPLAY_WINDOW_MS + 1)):
        with pytest.raises(BridgeAuthError):
            bridge_hmac.verify(BODY, signed_headers(ts=NOW + delta), keys=KEYS, now_ms=NOW)


def test_non_numeric_timestamp():
    headers = signed_headers()
    headers["x-hc-timestamp"] = "not-a-number"
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, headers, keys=KEYS, now_ms=NOW)


def test_bad_signature_format():
    headers = signed_headers()
    headers["x-hc-signature"] = headers["x-hc-signature"].removeprefix("sha256=")
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, headers, keys=KEYS, now_ms=NOW)


def test_missing_headers():
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, {}, keys=KEYS, now_ms=NOW)


def test_non_ascii_signature_is_auth_error_not_typeerror():
    # compare_digest(str, str) raises TypeError on non-ASCII — must surface
    # as a 401-mapped BridgeAuthError, never a 500
    headers = signed_headers()
    headers["x-hc-signature"] = "sha256=Ā" + headers["x-hc-signature"][8:]
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, headers, keys=KEYS, now_ms=NOW)


def test_no_keys_configured():
    with pytest.raises(BridgeAuthError):
        bridge_hmac.verify(BODY, signed_headers(), keys={}, now_ms=NOW)

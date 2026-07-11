"""HMAC verification for BRIDGE-CONTRACT-v1 webhooks (HybridCard → Looper).

The contract is FROZEN — this module mirrors the sender byte-for-byte
(new-card src/lib/bridge/hmac.ts): signature base = "{timestamp_ms}.{raw_body}",
HMAC-SHA256 lowercase hex prefixed "sha256=", headers X-HC-Signature /
X-HC-Key-Id / X-HC-Timestamp (unix epoch milliseconds, as a string),
replay window ±5 minutes, constant-time compare.
"""
import hashlib
import hmac
import os
import time

REPLAY_WINDOW_MS = 5 * 60 * 1000  # ±300_000 ms, per contract


class BridgeAuthError(Exception):
    """Any HMAC/timestamp/key failure. Routes map this to 401."""


def load_keys() -> dict[str, str]:
    """key_id -> secret. All ids currently share HYBRIDCARD_INGEST_SECRET;
    the dict shape is the rotation seam for future per-id secrets."""
    secret = os.getenv("HYBRIDCARD_INGEST_SECRET", "")
    ids = [i.strip() for i in os.getenv("HYBRIDCARD_KEY_IDS", "hc-1").split(",") if i.strip()]
    return {kid: secret for kid in ids if secret}


def verify(raw_body: bytes, headers, *, keys: dict[str, str] | None = None,
           now_ms: int | None = None) -> str:
    """Verify X-HC-* headers over the RAW request body bytes.

    Returns the key id on success; raises BridgeAuthError otherwise.
    `headers` is any case-insensitive mapping (Starlette Headers qualifies).
    """
    keys = keys if keys is not None else load_keys()
    sig = headers.get("x-hc-signature") or ""
    kid = headers.get("x-hc-key-id") or ""
    ts = headers.get("x-hc-timestamp") or ""

    if not sig.startswith("sha256="):
        raise BridgeAuthError("bad signature format")
    if kid not in keys:
        raise BridgeAuthError("unknown key id")
    try:
        ts_num = int(ts)
    except ValueError:
        raise BridgeAuthError("non-numeric timestamp")
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    if abs(now - ts_num) > REPLAY_WINDOW_MS:
        raise BridgeAuthError("timestamp outside replay window")

    expected = hmac.new(keys[kid].encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    # compare as bytes: compare_digest raises TypeError on non-ASCII str input,
    # which would turn a garbage header into a 500 instead of a 401
    got = sig[len("sha256="):].encode("utf-8", "replace")
    if not hmac.compare_digest(got, expected.encode()):
        raise BridgeAuthError("signature mismatch")
    return kid


def sign(raw_body: bytes, secret: str, key_id: str = "hc-1",
         timestamp_ms: int | None = None) -> dict[str, str]:
    """Python twin of the sender's signBody() — used by tests and the
    manual helper (tests/send_signed_event.py), never by the receiver path."""
    ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return {"X-HC-Signature": f"sha256={mac}", "X-HC-Key-Id": key_id, "X-HC-Timestamp": ts}

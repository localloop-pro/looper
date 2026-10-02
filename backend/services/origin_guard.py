"""Origin lock (looper#28, BLIND-SPOTS §3.12): only the Cloudflare Worker at
api.localloop.ai may reach this API.

The Worker sets `x-looper-origin-key` from its `ORIGIN_KEY` secret on every
proxied request (and replaces any value a caller sent). When
`LOOPER_ORIGIN_KEY` is set here, a request without the same value gets 403, so
the plain-HTTP origin URL stops being a way around Cloudflare — and only then
is `LOOPER_CLIENT_IP_HEADER=cf-connecting-ip` safe to trust for the per-IP
read limit (services/edge_boundary.py).

  LOOPER_ORIGIN_KEY   unset/blank = off (behaviour unchanged). Same random
                      value as the Worker's ORIGIN_KEY secret.

`GET /health` stays open for the Coolify/Docker health check. Register this
AFTER PublicReadBoundary and BEFORE CORSMiddleware in main.py: CORS and
correlation then still wrap the 403, and a rejected caller never spends a
rate-limit bucket or gets a cached answer.
"""
from __future__ import annotations

import hmac
import os

ORIGIN_KEY_HEADER = "x-looper-origin-key"
EXEMPT_PATHS = frozenset({"/health"})

_HEADER_BYTES = ORIGIN_KEY_HEADER.encode("latin-1")
_BODY = b'{"detail":"forbidden"}'


def expected_key() -> bytes:
    return (os.getenv("LOOPER_ORIGIN_KEY") or "").strip().encode("utf-8")


class OriginKeyGuard:
    """Pure ASGI middleware. Reads the env per request so tests (and an
    unset → set rollout without code changes) need no re-import."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        expected = expected_key()
        if not expected or scope.get("path") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        sent = b""
        for name, value in scope.get("headers") or []:
            if name == _HEADER_BYTES:
                sent = value
                break
        if hmac.compare_digest(sent, expected):
            await self.app(scope, receive, send)
            return

        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_BODY)).encode()),
                (b"cache-control", b"no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": _BODY})

"""E6 — privacy-safe request correlation and structured trace records.

One convention across browser, gateway, bridge, HybridCard and Looper
(docs/E6-RELEASE-GATE.md §1):

- HTTP hops carry `X-Request-ID`. An inbound value is kept only if it is an
  opaque token (8-128 chars of [A-Za-z0-9._:-] with at least one letter, so a
  dictated phone number can never become a trace key). Anything else is
  replaced with a fresh uuid4 hex. The canonical id is written back into the
  request scope, so every inner layer sees the same value, and echoed on the
  response.
- Bridge events are joined on the sender's `eventId` (the frozen
  BRIDGE-CONTRACT-v1 payload already carries it; no header is added).
- One JSON line per request (`kind: "http"`) and per bridge receipt
  (`kind: "bridge"`) goes to the `looper.trace` logger. The records hold
  only an allowlist of fields: no query string, raw path, client IP,
  user agent, cookies, authorization header, body or business data.
  Each line has a fixed field set and is bounded in size; retention is the
  log sink's (Coolify) rotation, never this process.

`LOOPER_TRACE_LOG=off` silences the records (rollback switch); the
`X-Request-ID` echo always stays on.
"""
import contextvars
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone

from starlette.datastructures import MutableHeaders

REQUEST_ID_HEADER = "x-request-id"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_HAS_LETTER_RE = re.compile(r"[A-Za-z]")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "looper_request_id", default=None)

logger = logging.getLogger("looper.trace")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def trace_enabled() -> bool:
    return os.getenv("LOOPER_TRACE_LOG", "on").strip().lower() not in {"off", "0", "false", "no"}


def resolve_request_id(inbound: str | None) -> str:
    """Keep a safe opaque inbound id, otherwise mint a new one."""
    value = (inbound or "").strip()
    if _REQUEST_ID_RE.match(value) and _HAS_LETTER_RE.search(value):
        return value
    return uuid.uuid4().hex


def safe_event_id(value) -> str | None:
    """Bridge eventId as a join key: opaque token or nothing."""
    if isinstance(value, str) and _EVENT_ID_RE.match(value):
        return value
    return None


def emit(record: dict) -> None:
    """Write one trace record. Never raises, never blocks the request."""
    if not trace_enabled():
        return
    try:
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                  **record}
        logger.info(json.dumps(record, separators=(",", ":"), sort_keys=True))
    except Exception:
        pass


def emit_bridge(*, receiver: str, outcome: str, event_type: str | None = None,
                event_id=None, sender_updated_at: datetime | None = None) -> None:
    """Bridge receipt record. delivery_age_s = receive time - the sender's
    payload updated_at (naive UTC), i.e. how long the event took to land,
    including every outbox retry. The X-HC-Timestamp header cannot be used:
    the sender re-signs each retry with a fresh timestamp."""
    age = None
    if sender_updated_at is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age = round(max(0.0, (now - sender_updated_at).total_seconds()), 3)
    emit({
        "kind": "bridge",
        "receiver": receiver,
        "rid": current_request_id.get(),
        "event_id": safe_event_id(event_id),
        "event_type": event_type,
        "outcome": outcome,
        "delivery_age_s": age,
    })


class CorrelationMiddleware:
    """Pure ASGI: canonical X-Request-ID + one `kind: http` record per request.

    Register it LAST in main.py so it is the outermost layer: CORS
    rejections, cache hits and rate-limit answers all get an id and a record.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        inbound = None
        for key, value in scope.get("headers") or []:
            if key == b"x-request-id":
                inbound = value.decode("latin-1")
                break
        request_id = resolve_request_id(inbound)

        # Rewrite the inbound header so inner layers agree on one id.
        headers = [(k, v) for k, v in (scope.get("headers") or []) if k != b"x-request-id"]
        headers.append((b"x-request-id", request_id.encode("latin-1")))
        scope["headers"] = headers
        scope.setdefault("state", {})["request_id"] = request_id
        token = current_request_id.set(request_id)

        info = {"status": 500, "cache": None}
        started = time.perf_counter()

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                out = MutableHeaders(scope=message)
                out[REQUEST_ID_HEADER] = request_id
                info["status"] = message["status"]
                info["cache"] = out.get("x-looper-cache")
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            # Route template only (/api/search, /api/users/{user_id}, or /web
            # for the static mount) — never the raw path or query, which can
            # carry free text.
            route = getattr(scope.get("route"), "path", None)
            emit({
                "kind": "http",
                "rid": request_id,
                "method": scope.get("method"),
                "route": route or "unmatched",
                "status": info["status"],
                "dur_ms": round((time.perf_counter() - started) * 1000, 2),
                "cache": info["cache"],
            })
            current_request_id.reset(token)

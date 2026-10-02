"""Public read-path boundary (issue #8, Functions epic E4): request
correlation, per-IP rate limiting and a short-TTL response cache for the
anonymous read endpoints.

Everything here sits IN FRONT of the FastAPI routes and never changes what a
route computes: ranking, the TypeDB→SQLite fallback and telemetry stay in
routes/*.py. The layer only decides whether to answer from a recent copy,
refuse an abusive caller, or label the response.

Both behaviour switches default OFF so merging this changes nothing in
production until the owner accepts the E1 ADR (localloop.pro-main#100):

  LOOPER_READ_CACHE_TTL_S          0 = off. Seconds a cached answer is fresh.
  LOOPER_READ_CACHE_STALE_S        Extra seconds a stale copy may be served
                                   when the route errors (5xx). Default 60.
  LOOPER_READ_CACHE_MAX_ENTRIES    LRU bound. Default 512.
  LOOPER_READ_RATE_LIMIT_PER_MIN   0 = off. Requests per minute per client.
  LOOPER_CLIENT_IP_HEADER          Header carrying the real client IP, e.g.
                                   cf-connecting-ip. ONLY set this when the
                                   origin is reachable solely through that
                                   proxy — otherwise callers can spoof it.

Policy table (docs/EDGE-READ-BOUNDARY.md explains each row):

  cacheable  /api/search, /api/discover, /api/businesses
  no-store   /api/reviews/*, /api/ingest/*, /health
  rate limit every GET/HEAD under /api/ (writes and bridge receivers untouched)

Cache key = path + the route's ranking-relevant query params, in request
order, + the TypeDB engine switch + a write generation. `session` and
`intent` (telemetry only) and unknown params are deliberately NOT in the key;
no identity, cookie, discount, source or paid status ever is.
"""
from __future__ import annotations

import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from urllib.parse import parse_qsl

from starlette.datastructures import Headers, MutableHeaders

# Ranking-relevant params per cacheable route. Anything else a caller sends is
# ignored by FastAPI too, so leaving it out of the key cannot mix answers.
CACHEABLE_PARAMS: dict[str, tuple[str, ...]] = {
    "/api/search": ("q", "lat", "lng", "radius_km", "category", "limit"),
    "/api/discover": ("suburb", "lat", "lng", "radius_km", "category", "limit"),
    "/api/businesses": ("category", "lat", "lng", "radius_km", "limit"),
}

# Reads that carry per-person or operational data: never cached anywhere.
NO_STORE_PREFIXES = ("/api/reviews/", "/api/ingest/", "/health")

SAFE_METHODS = {"GET", "HEAD"}
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, "") or default))
    except ValueError:
        return default


class ReadCache:
    """Small thread-safe LRU of finished 200 responses."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple, tuple[float, int, list, bytes]] = OrderedDict()
        self.generation = 0

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.generation = 0

    def invalidate(self) -> None:
        """A write happened: every cached answer may now be wrong."""
        with self._lock:
            self._entries.clear()
            self.generation += 1

    def get(self, key: tuple, ttl: int, stale: int, *, allow_stale: bool = False):
        now = time.monotonic()
        with self._lock:
            hit = self._entries.get(key)
            if hit is None:
                return None
            stored_at, status, headers, body = hit
            age = now - stored_at
            if age > ttl + stale:
                del self._entries[key]
                return None
            if age > ttl and not allow_stale:
                return None
            self._entries.move_to_end(key)
            return status, headers, body

    def put(self, key: tuple, status: int, headers: list, body: bytes, max_entries: int) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic(), status, headers, body)
            self._entries.move_to_end(key)
            while len(self._entries) > max_entries:
                self._entries.popitem(last=False)


class RateLimiter:
    """Fixed one-minute window per client key, bounded memory."""

    MAX_KEYS = 10_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: OrderedDict[str, tuple[int, int]] = OrderedDict()

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()

    def hit(self, key: str, limit: int) -> tuple[bool, int]:
        """Count one request. Returns (allowed, seconds until the window resets)."""
        now = time.time()
        window = int(now // 60)
        with self._lock:
            seen_window, count = self._windows.get(key, (window, 0))
            if seen_window != window:
                count = 0
            count += 1
            self._windows[key] = (window, count)
            self._windows.move_to_end(key)
            while len(self._windows) > self.MAX_KEYS:
                self._windows.popitem(last=False)
        retry_after = max(1, int(60 - (now % 60)))
        return count <= limit, retry_after


read_cache = ReadCache()
rate_limiter = RateLimiter()


def cache_key(path: str, query_string: bytes) -> tuple:
    allowed = CACHEABLE_PARAMS[path]
    params = tuple((k, v) for k, v in parse_qsl(query_string.decode("latin-1"), keep_blank_values=True)
                   if k in allowed)
    engine = os.getenv("TYPEDB_ENABLED", "false").lower() == "true"
    return (path, params, engine, read_cache.generation)


def client_key(scope, headers: Headers) -> str:
    header = (os.getenv("LOOPER_CLIENT_IP_HEADER") or "").strip().lower()
    if header:
        value = headers.get(header, "").split(",")[0].strip()
        if value:
            return value
    client = scope.get("client")
    return client[0] if client else "unknown"


class PublicReadBoundary:
    """Pure ASGI middleware. Register it BEFORE CORSMiddleware so CORS stays
    outermost and every answer (HIT, 429, STALE) still gets CORS headers."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        method = scope["method"]
        path = scope["path"]
        inbound_id = headers.get("x-request-id", "")
        request_id = inbound_id if _REQUEST_ID_RE.match(inbound_id) else uuid.uuid4().hex

        def decorate(raw_headers, cache_state=None, cache_control=None):
            out = MutableHeaders(raw=list(raw_headers))
            out["x-request-id"] = request_id
            if cache_state:
                out["x-looper-cache"] = cache_state
            if cache_control:
                out["cache-control"] = cache_control
            return out.raw

        # Writes: pass through untouched, then invalidate on success.
        if method not in SAFE_METHODS:
            status_holder = {}

            async def send_write(message):
                if message["type"] == "http.response.start":
                    status_holder["status"] = message["status"]
                    message = {**message, "headers": decorate(message["headers"])}
                await send(message)

            await self.app(scope, receive, send_write)
            if path.startswith("/api/") and status_holder.get("status", 500) < 400:
                read_cache.invalidate()
            return

        # Rate limit public reads.
        limit = _env_int("LOOPER_READ_RATE_LIMIT_PER_MIN", 0)
        if limit and path.startswith("/api/"):
            allowed, retry_after = rate_limiter.hit(client_key(scope, headers), limit)
            if not allowed:
                body = b'{"detail":"Too many requests. Please slow down and try again shortly."}'
                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": decorate([
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"retry-after", str(retry_after).encode()),
                    ], cache_control="no-store"),
                })
                await send({"type": "http.response.body", "body": body})
                return

        if path in CACHEABLE_PARAMS and method == "GET":
            await self._cached_read(scope, receive, send, headers, decorate)
            return

        no_store = path.startswith(NO_STORE_PREFIXES)

        async def send_plain(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": decorate(
                    message["headers"], cache_control="no-store" if no_store else None)}
            await send(message)

        await self.app(scope, receive, send_plain)

    async def _cached_read(self, scope, receive, send, headers, decorate):
        ttl = _env_int("LOOPER_READ_CACHE_TTL_S", 0)
        if not ttl:
            async def send_off(message):
                if message["type"] == "http.response.start":
                    message = {**message, "headers": decorate(message["headers"], cache_control="no-store")}
                await send(message)

            await self.app(scope, receive, send_off)
            return

        stale = _env_int("LOOPER_READ_CACHE_STALE_S", 60)
        max_entries = _env_int("LOOPER_READ_CACHE_MAX_ENTRIES", 512) or 1
        public_cc = f"public, max-age=0, s-maxage={ttl}, stale-if-error={stale}"
        key = cache_key(scope["path"], scope.get("query_string", b""))

        directives = (headers.get("cache-control", "") + "," + headers.get("pragma", "")).lower()
        revalidate = "no-cache" in directives or "no-store" in directives
        bypass = "authorization" in headers  # never share an answer to an identified caller

        async def replay(entry, state):
            status, raw_headers, body = entry
            await send({"type": "http.response.start", "status": status,
                        "headers": decorate(raw_headers, state, public_cc)})
            await send({"type": "http.response.body", "body": body})

        if not (revalidate or bypass):
            entry = read_cache.get(key, ttl, stale)
            if entry:
                await replay(entry, "HIT")
                return

        # Buffer the route's answer so a 5xx can be swapped for a stale copy.
        start: dict = {}
        chunks: list[bytes] = []

        async def capture(message):
            if message["type"] == "http.response.start":
                start.update(message)
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        try:
            await self.app(scope, receive, capture)
            failed = start.get("status", 500) >= 500
        except Exception:
            failed = True
            if not bypass:
                entry = read_cache.get(key, ttl, stale, allow_stale=True)
                if entry:
                    await replay(entry, "STALE")
                    return
            raise

        if failed and not bypass:
            entry = read_cache.get(key, ttl, stale, allow_stale=True)
            if entry:
                await replay(entry, "STALE")
                return

        status = start.get("status", 500)
        body = b"".join(chunks)
        cacheable = status == 200 and not bypass
        if cacheable:
            read_cache.put(key, status, list(start.get("headers", [])), body, max_entries)
        state = "BYPASS" if bypass else "MISS"
        await send({"type": "http.response.start", "status": status,
                    "headers": decorate(start.get("headers", []), state,
                                        public_cc if cacheable else "no-store")})
        await send({"type": "http.response.body", "body": body})

"""E6 (issue #9) — privacy-safe correlation and trace records.

Every request gets one canonical X-Request-ID and one `kind: http` JSON
record; every bridge receipt gets one `kind: bridge` record joined on the
sender's eventId. Records carry an allowlist of fields only — no query
text, raw path, IP, user agent, auth header, body or business data.
"""
import ast
import json
import logging
import pathlib
import re

import pytest

from services import correlation
from tests.conftest import sample_deal_payload, signed_post

HTTP_KEYS = {"ts", "kind", "rid", "method", "route", "status", "dur_ms", "cache"}
BRIDGE_KEYS = {"ts", "kind", "receiver", "rid", "event_id", "event_type",
               "outcome", "delivery_age_s"}
HEX32 = re.compile(r"^[0-9a-f]{32}$")


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture()
def trace(monkeypatch):
    monkeypatch.delenv("LOOPER_TRACE_LOG", raising=False)
    handler = _Capture()
    correlation.logger.addHandler(handler)
    yield handler
    correlation.logger.removeHandler(handler)


def records(handler, kind):
    return [r for r in map(json.loads, handler.lines) if r["kind"] == kind]


# ---------------------------------------------------------------- request id

def test_request_id_generated_when_absent(client, trace):
    resp = client.get("/health")
    rid = resp.headers["x-request-id"]
    assert HEX32.match(rid)
    (rec,) = records(trace, "http")
    assert rec["rid"] == rid
    assert set(rec) == HTTP_KEYS
    assert rec["route"] == "/health" and rec["status"] == 200 and rec["method"] == "GET"


def test_safe_inbound_request_id_is_echoed(client, trace):
    rid = "gw-7f3a9c:01.abc"
    resp = client.get("/health", headers={"X-Request-ID": rid})
    assert resp.headers["x-request-id"] == rid
    assert records(trace, "http")[0]["rid"] == rid


@pytest.mark.parametrize("bad", [
    "0412345678",                 # dictated mobile — digits only
    "+61 412 345 678",            # mobile with spaces/plus
    "bill@example.com",           # email
    "short1",                     # under 8 chars
    "a" * 129,                    # over 128 chars
    "abc def ghi",                # whitespace
    "abc<script>xyz",             # markup
    "Bearer abcdefghijk",         # credential-shaped
])
def test_unsafe_inbound_request_id_is_replaced(client, trace, bad):
    resp = client.get("/health", headers={"X-Request-ID": bad})
    rid = resp.headers["x-request-id"]
    assert rid != bad and HEX32.match(rid)
    assert bad not in "\n".join(trace.lines)


def test_inner_layers_see_the_canonical_id():
    """The resolved id is written back into the scope, so anything inside
    (route, the #8 read boundary) reads the same value the caller gets."""
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    def echo(request):
        return PlainTextResponse(request.headers.get("x-request-id", ""))

    app = Starlette(routes=[Route("/", echo)])
    app.add_middleware(correlation.CorrelationMiddleware)
    c = TestClient(app)
    resp = c.get("/", headers={"X-Request-ID": "0412345678"})
    assert resp.text == resp.headers["x-request-id"]
    assert HEX32.match(resp.text)
    resp = c.get("/", headers={"X-Request-ID": "trace-abc-123"})
    assert resp.text == "trace-abc-123" == resp.headers["x-request-id"]


# ---------------------------------------------------------------- no leakage

def test_http_record_never_holds_query_ip_ua_or_auth(client, trace):
    secret_bits = ["bill@example.com", "0412 345 678", "SuperSecretToken123",
                   "testclient", "Mozilla/5.0-unique-ua"]
    resp = client.get("/api/search",
                      params={"q": "café near bill@example.com 0412 345 678"},
                      headers={"Authorization": "Bearer SuperSecretToken123",
                               "User-Agent": "Mozilla/5.0-unique-ua",
                               "Cookie": "sid=SuperSecretToken123"})
    assert resp.status_code == 200
    blob = "\n".join(trace.lines)
    for bit in secret_bits:
        assert bit not in blob
    (rec,) = records(trace, "http")
    assert set(rec) == HTTP_KEYS and rec["route"] == "/api/search"


def test_route_template_not_raw_path(client, trace):
    client.get("/api/reviews/12345")
    client.get("/api/does-not-exist/bill@example.com")
    client.get("/web/jarvis/does-not-exist.js")
    routes = [r["route"] for r in records(trace, "http")]
    assert routes == ["/api/reviews/{business_id}", "unmatched", "/web"]
    assert "bill@example.com" not in "\n".join(trace.lines)


def test_record_is_bounded(client, trace):
    client.get("/health", headers={"X-Request-ID": "r" * 128})
    assert all(len(line) < 512 for line in trace.lines)


def test_cors_rejected_preflight_still_traced(client, trace):
    resp = client.options("/api/search", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET"})
    assert resp.status_code == 400
    assert HEX32.match(resp.headers["x-request-id"])
    assert records(trace, "http")[0]["status"] == 400


def test_trace_off_keeps_header_but_logs_nothing(client, trace, monkeypatch):
    monkeypatch.setenv("LOOPER_TRACE_LOG", "off")
    resp = client.get("/health")
    assert HEX32.match(resp.headers["x-request-id"])
    assert trace.lines == []


_BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_uvicorn_access_log_off_in_main():
    """uvicorn's default access line holds the client IP and the raw query
    string. `python main.py` must run with access_log=False; the allowlisted
    trace record replaces it."""
    tree = ast.parse((_BACKEND / "main.py").read_text())
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == "run"
            and getattr(n.func.value, "id", None) == "uvicorn"]
    assert runs
    for call in runs:
        kw = {k.arg: k.value for k in call.keywords}
        assert isinstance(kw.get("access_log"), ast.Constant)
        assert kw["access_log"].value is False


def final_cmd(dockerfile: str) -> list[str]:
    """The exec-form argv of the last CMD instruction (the one Docker runs),
    with backslash line continuations joined."""
    joined = re.sub(r"\\\n", " ", dockerfile)
    cmds = [line.strip()[3:].strip() for line in joined.splitlines()
            if line.strip().upper().startswith("CMD ")]
    assert cmds, "Dockerfile has no CMD"
    argv = json.loads(cmds[-1])  # shell form would not parse: keep exec form
    assert isinstance(argv, list) and all(isinstance(a, str) for a in argv)
    return argv


def test_uvicorn_access_log_off_in_dockerfile():
    """looper#62: the production image's CMD must run uvicorn with
    --no-access-log, or every request writes the client IP and the raw query
    string (dictated phone numbers/emails) to the Coolify logs."""
    argv = final_cmd((_BACKEND / "Dockerfile").read_text())
    assert argv[0] == "uvicorn"
    assert "--no-access-log" in argv
    assert "--access-log" not in argv


def test_final_cmd_check_catches_old_cmd():
    old = 'FROM x\nCMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
    assert "--no-access-log" not in final_cmd(old)
    # Only the last CMD counts; an earlier compliant one does not hide it.
    two = 'CMD ["uvicorn", "main:app", "--no-access-log"]\n' + old
    assert "--no-access-log" not in final_cmd(two)


# ---------------------------------------------------------------- bridge

def test_bridge_processed_then_duplicate(client, trace):
    payload = sample_deal_payload(eventId="evt-trace-1",
                                  updated_at="2026-01-01T00:00:00.000Z")
    first = signed_post(client, "/api/ingest/hybridcard-deal", payload)
    replay = signed_post(client, "/api/ingest/hybridcard-deal", payload)
    assert first.status_code == replay.status_code == 200

    b1, b2 = records(trace, "bridge")
    assert set(b1) == BRIDGE_KEYS
    assert (b1["outcome"], b2["outcome"]) == ("processed", "duplicate")
    assert b1["event_id"] == b2["event_id"] == "evt-trace-1"
    assert b1["event_type"] == "deal.upserted"
    assert b1["receiver"] == "hybridcard-deal"
    assert b1["rid"] == first.headers["x-request-id"]
    assert b1["delivery_age_s"] > 0
    blob = "\n".join(trace.lines)
    for field in ("Bondi Cafe", "card-abc123", "deal-xyz789", "hybridcard.ai",
                  "Lunch deal", "sha256="):
        assert field not in blob


def test_bridge_stale_and_removed(client, trace):
    signed_post(client, "/api/ingest/hybridcard-card",
                {**sample_deal_payload(eventId="c-new", updated_at="2026-07-12T00:00:00Z"),
                 "slug": "bondi-cafe"})
    signed_post(client, "/api/ingest/hybridcard-card",
                {**sample_deal_payload(eventId="c-old", active=False,
                                       updated_at="2026-07-10T00:00:00Z"),
                 "slug": "bondi-cafe"})
    new, old = records(trace, "bridge")
    assert (new["outcome"], new["event_type"]) == ("processed", "card.upserted")
    assert (old["outcome"], old["event_type"]) == ("stale_skipped", "card.removed")


def test_bridge_rejections_are_traced_without_event_id(client, trace):
    bad_sig = signed_post(client, "/api/ingest/hybridcard-deal",
                          sample_deal_payload(eventId="evt-tamper"), tamper=True)
    bad_body = signed_post(client, "/api/ingest/hybridcard-deal", {"eventId": "x"})
    assert (bad_sig.status_code, bad_body.status_code) == (401, 422)
    outcomes = [(r["outcome"], r["event_id"]) for r in records(trace, "bridge")]
    assert outcomes == [("unauthorized", None), ("invalid_payload", None)]
    assert "evt-tamper" not in "\n".join(trace.lines)
    statuses = [r["status"] for r in records(trace, "http")]
    assert statuses == [401, 422]


def test_unsafe_event_id_is_not_logged(client, trace):
    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(eventId="evt bill@example.com"))
    assert resp.status_code == 200
    (rec,) = records(trace, "bridge")
    assert rec["event_id"] is None
    assert "bill@example.com" not in "\n".join(trace.lines)


# ---------------------------------------------------------------- no regression

def test_tracing_does_not_change_search_order(client, db, monkeypatch):
    from models import Business
    for i, name in enumerate(["Cafe One", "Cafe Two", "Cafe Three"]):
        db.add(Business(name=name, category="café", suburb="Bondi",
                        lat=-33.89 + i * 0.01, lng=151.27, source="manual"))
    db.commit()
    params = {"q": "café", "lat": -33.89, "lng": 151.27}
    monkeypatch.setenv("LOOPER_TRACE_LOG", "on")
    on = client.get("/api/search", params=params).json()["results"]
    monkeypatch.setenv("LOOPER_TRACE_LOG", "off")
    off = client.get("/api/search", params=params).json()["results"]
    assert [r["name"] for r in on] == [r["name"] for r in off]
    assert len(on) == 3


# ---------------------------------------------------------------- with #8 boundary

@pytest.fixture()
def boundary(monkeypatch):
    from services import edge_boundary
    edge_boundary.read_cache.clear()
    edge_boundary.rate_limiter.clear()
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "30")
    monkeypatch.setenv("LOOPER_READ_RATE_LIMIT_PER_MIN", "2")
    yield
    edge_boundary.read_cache.clear()
    edge_boundary.rate_limiter.clear()


def test_one_id_through_read_boundary_and_hits_are_traced(client, trace, boundary):
    """The #8 boundary echoes the id it sees; correlation rewrote it first,
    so a phone-shaped id never reaches the response and only one value is
    sent. Cache HITs and 429s still produce a trace record."""
    answers = [client.get("/api/search", params={"q": "café"},
                          headers={"X-Request-ID": "0412345678"}) for _ in range(3)]
    for resp in answers:
        ids = resp.headers.get_list("x-request-id")
        assert len(ids) == 1 and HEX32.match(ids[0])
    recs = records(trace, "http")
    assert [r["rid"] for r in recs] == [a.headers["x-request-id"] for a in answers]
    assert [(r["status"], r["cache"]) for r in recs] == [
        (200, "MISS"), (200, "HIT"), (429, None)]
    assert "0412345678" not in "\n".join(trace.lines)

"""looper#28: origin locked to the Cloudflare Worker (shared origin key) and
no localhost CORS in production."""
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from services.cors_policy import PRODUCTION_ORIGINS, cors_options, dev_origins
from services.origin_guard import ORIGIN_KEY_HEADER

KEY = "test-origin-key-0123456789"


@pytest.fixture()
def key_set(monkeypatch):
    monkeypatch.setenv("LOOPER_ORIGIN_KEY", KEY)


@pytest.fixture()
def key_unset(monkeypatch):
    monkeypatch.delenv("LOOPER_ORIGIN_KEY", raising=False)


# --- origin key set ----------------------------------------------------------

def test_missing_key_is_403(client, key_set):
    resp = client.get("/api/search", params={"q": "cafe"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "forbidden"}
    assert KEY not in resp.text


def test_wrong_key_is_403(client, key_set):
    resp = client.get("/api/search", params={"q": "cafe"}, headers={ORIGIN_KEY_HEADER: "nope"})
    assert resp.status_code == 403


def test_key_prefix_is_403(client, key_set):
    resp = client.get("/api/search", params={"q": "cafe"}, headers={ORIGIN_KEY_HEADER: KEY[:-1]})
    assert resp.status_code == 403


def test_right_key_is_200(client, key_set):
    resp = client.get("/api/search", params={"q": "cafe"}, headers={ORIGIN_KEY_HEADER: KEY})
    assert resp.status_code == 200


def test_writes_without_key_are_403_before_the_route(client, key_set):
    # Bridge receivers and public writes are locked too; the guard answers
    # before HMAC or body validation, so an empty body still gets 403.
    for p in ("/api/ingest/hybridcard-deal", "/api/reviews"):
        assert client.post(p, content=b"{}").status_code == 403


def test_health_is_exempt(client, key_set):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_403_keeps_request_id_and_cors(client, key_set):
    resp = client.get("/api/search", params={"q": "cafe"},
                      headers={"Origin": "https://localloop.ai", "X-Request-ID": "turn-abc12345"})
    assert resp.status_code == 403
    assert resp.headers["x-request-id"] == "turn-abc12345"
    assert resp.headers["access-control-allow-origin"] == "https://localloop.ai"


def test_403_does_not_spend_the_rate_limit(client, key_set, monkeypatch):
    from services.edge_boundary import rate_limiter
    rate_limiter.clear()
    monkeypatch.setenv("LOOPER_READ_RATE_LIMIT_PER_MIN", "2")
    try:
        for _ in range(5):
            assert client.get("/api/search", params={"q": "x"}).status_code == 403
        ok = client.get("/api/search", params={"q": "x"}, headers={ORIGIN_KEY_HEADER: KEY})
        assert ok.status_code == 200
    finally:
        rate_limiter.clear()


def test_blank_env_value_means_unset(client, monkeypatch):
    monkeypatch.setenv("LOOPER_ORIGIN_KEY", "   ")
    assert client.get("/api/search", params={"q": "cafe"}).status_code == 200


# --- origin key unset: unchanged ---------------------------------------------

def test_unset_key_no_header_is_200(client, key_unset):
    assert client.get("/api/search", params={"q": "cafe"}).status_code == 200


def test_unset_key_ignores_any_header(client, key_unset):
    resp = client.get("/api/search", params={"q": "cafe"}, headers={ORIGIN_KEY_HEADER: "anything"})
    assert resp.status_code == 200


def test_unset_key_writes_unchanged(client, key_unset, monkeypatch):
    monkeypatch.delenv("LOOPER_PUBLIC_WRITES", raising=False)
    # Same answer as main before #28: the looper#27 write guard, not this one.
    assert client.post("/api/reviews", json={}).status_code == 403
    assert client.post("/api/reviews", json={}).json() == {"detail": "public writes are disabled"}


# --- CORS --------------------------------------------------------------------

LOCAL = "http://localhost:5173"


def test_production_list_is_https_only():
    assert PRODUCTION_ORIGINS
    assert all(o.startswith("https://") for o in PRODUCTION_ORIGINS)
    assert "https://localloop.ai" in PRODUCTION_ORIGINS


def test_credentials_off():
    assert cors_options()["allow_credentials"] is False


def test_live_app_rejects_localhost(client, monkeypatch):
    # main.app was built at import with LOOPER_DEV_ORIGINS unset (conftest).
    resp = client.get("/health", headers={"Origin": LOCAL})
    assert "access-control-allow-origin" not in resp.headers
    pre = client.options("/api/search", headers={"Origin": LOCAL, "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in pre.headers
    assert "access-control-allow-credentials" not in pre.headers


def test_live_app_allows_production_host(client):
    resp = client.get("/health", headers={"Origin": "https://www.localloop.ai"})
    assert resp.headers["access-control-allow-origin"] == "https://www.localloop.ai"
    assert "access-control-allow-credentials" not in resp.headers


def _app_with_cors():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, **cors_options())

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


def test_localhost_blocked_when_dev_origins_unset(monkeypatch):
    monkeypatch.delenv("LOOPER_DEV_ORIGINS", raising=False)
    resp = _app_with_cors().get("/ping", headers={"Origin": LOCAL})
    assert "access-control-allow-origin" not in resp.headers


def test_localhost_allowed_only_when_listed(monkeypatch):
    monkeypatch.setenv("LOOPER_DEV_ORIGINS", " http://localhost:3000 , http://localhost:5173/ ,")
    client = _app_with_cors()
    resp = client.get("/ping", headers={"Origin": LOCAL})
    assert resp.headers["access-control-allow-origin"] == LOCAL
    other = client.get("/ping", headers={"Origin": "http://localhost:8080"})
    assert "access-control-allow-origin" not in other.headers


def test_dev_origins_rejects_wildcard(monkeypatch):
    monkeypatch.setenv("LOOPER_DEV_ORIGINS", "*,http://localhost:3000")
    assert dev_origins() == ["http://localhost:3000"]

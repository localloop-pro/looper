"""PR A — api.localloop.ai public front door.

Covers Accept negotiation, LOOPER_FRONTDOOR_LIVE dark/live, HEAD, trailing
slash host leak, /api/* stays JSON, and /health shape including commit.
"""
from __future__ import annotations

import json

import pytest

from public_surface import ROOT_JSON_KEYS, root_payload, wants_html

SSLIP = "http://looper-api.167.86.79.151.sslip.io"


@pytest.fixture()
def dark(monkeypatch):
    monkeypatch.setenv("LOOPER_FRONTDOOR_LIVE", "0")


@pytest.fixture()
def live(monkeypatch):
    monkeypatch.setenv("LOOPER_FRONTDOOR_LIVE", "1")


def _keys(resp) -> list[str]:
    return list(json.loads(resp.text).keys())


def _vary(resp) -> set[str]:
    raw = resp.headers.get("vary") or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


# --- Accept helpers ----------------------------------------------------------

@pytest.mark.parametrize("accept,expect_html", [
    (None, False),
    ("", False),
    ("*/*", False),
    ("application/json", False),
    ("text/html", True),
    ("text/html, application/json;q=0.9", True),
    ("text/html;q=0.8, application/json", False),
    ("text/html;q=0.5, application/json;q=0.5", False),  # tie → JSON
    ("application/json;q=0.1, text/html;q=0.9", True),
    ("text/plain", False),
])
def test_wants_html_matrix(accept, expect_html):
    assert wants_html(accept) is expect_html


# --- Dark (flag off): today's JSON, no new surfaces --------------------------

def test_dark_root_json_key_order(client, dark):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == root_payload()
    assert _keys(resp) == list(ROOT_JSON_KEYS)


@pytest.mark.parametrize("accept", [
    None,
    "*/*",
    "application/json",
    "text/html",
    "text/html, application/json;q=0.9",
    "text/html;q=0.8, application/json",
])
def test_dark_root_never_html(client, dark, accept):
    headers = {} if accept is None else {"Accept": accept}
    resp = client.get("/", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert _keys(resp) == list(ROOT_JSON_KEYS)


def test_dark_reference_and_crawler_files_404(client, dark):
    for path in ("/reference", "/robots.txt", "/llms.txt", "/sitemap.xml"):
        assert client.get(path).status_code == 404


def test_dark_docs_is_still_swagger(client, dark):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()
    assert resp.headers["content-type"].startswith("text/html")


# --- Live: negotiation + new surfaces ----------------------------------------

@pytest.mark.parametrize("accept", [None, "*/*", "application/json"])
def test_live_root_json_for_api_clients(client, live, accept):
    headers = {} if accept is None else {"Accept": accept}
    resp = client.get("/", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == root_payload()
    assert _keys(resp) == list(ROOT_JSON_KEYS)
    assert {"accept", "origin"} <= _vary(resp)


def test_live_root_html_when_browser_prefers_html(client, live):
    resp = client.get("/", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "LOOPER API" in resp.text
    assert {"accept", "origin"} <= _vary(resp)


def test_live_root_q_values_html_wins(client, live):
    resp = client.get("/", headers={"Accept": "text/html, application/json;q=0.9"})
    assert resp.headers["content-type"].startswith("text/html")


def test_live_root_q_values_json_wins(client, live):
    resp = client.get("/", headers={"Accept": "text/html;q=0.8, application/json"})
    assert resp.headers["content-type"].startswith("application/json")
    assert _keys(resp) == list(ROOT_JSON_KEYS)


def test_live_docs_redirects_to_reference(client, live):
    resp = client.get("/docs", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/reference"


def test_live_reference_ok(client, live):
    resp = client.get("/reference")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "openapi.json" in resp.text
    assert {"accept", "origin"} <= _vary(resp)


def test_live_crawler_files(client, live):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /api/" in robots.text

    llms = client.get("/llms.txt")
    assert llms.status_code == 200
    assert "LOOPER API" in llms.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "application/xml" in sitemap.headers["content-type"]
    assert "https://api.localloop.ai/reference" in sitemap.text


# --- OPTIONS (CORS) ----------------------------------------------------------

def test_options_root_with_origin(client, dark):
    resp = client.options(
        "/",
        headers={
            "Origin": "https://localloop.ai",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://localloop.ai"


def test_options_root_without_origin(client, dark):
    # No Origin → not a CORS preflight; route has no OPTIONS handler → 405.
    resp = client.options("/")
    assert resp.status_code in (200, 405)


def test_options_root_live_with_origin(client, live):
    resp = client.options(
        "/",
        headers={
            "Origin": "https://localloop.ai",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://localloop.ai"


# --- HEAD --------------------------------------------------------------------

def test_head_root_health_reference(client, live):
    for path in ("/", "/health", "/reference"):
        resp = client.head(path)
        assert resp.status_code == 200, path
        assert resp.content == b""


def test_head_root_and_health_when_dark(client, dark):
    assert client.head("/").status_code == 200
    assert client.head("/health").status_code == 200
    assert client.head("/reference").status_code == 404


# --- Trailing slash: never leak sslip / http absolute Location ---------------

@pytest.mark.parametrize("path", ["/docs/", "/health/"])
def test_trailing_slash_never_redirects_to_sslip(client, dark, path):
    # TestClient base_url is http://testserver; also probe with the real origin host.
    resp = client.get(path, follow_redirects=False)
    loc = resp.headers.get("location") or ""
    assert "sslip.io" not in loc
    assert not loc.startswith("http://")
    # Prefer no redirect at all (redirect_slashes=False → 404).
    assert resp.status_code != 307 or not loc


def test_trailing_slash_with_sslip_base_url(dark):
    from fastapi.testclient import TestClient
    from main import app

    c = TestClient(app, base_url=SSLIP)
    for path in ("/docs/", "/health/"):
        resp = c.get(path, follow_redirects=False)
        loc = (resp.headers.get("location") or "").lower()
        assert "sslip" not in loc
        assert not loc.startswith("http://")
        assert resp.status_code in (404, 405)


# --- /api/* stays JSON (HybridCard hard condition) ---------------------------

@pytest.mark.parametrize("accept", [None, "text/html", "*/*", "application/json"])
def test_api_search_stays_json(client, live, accept):
    headers = {} if accept is None else {"Accept": accept}
    resp = client.get("/api/search", params={"q": "cafe"}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert "results" in body
    # Must not grow Accept negotiation on /api/*
    vary = _vary(resp)
    assert "accept" not in vary


# --- /health shape (always on) -----------------------------------------------

def test_health_shape_includes_commit(client, dark, monkeypatch):
    monkeypatch.delenv("LOOPER_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    monkeypatch.setenv("LOOPER_COMMIT", "abcdef0123459999")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "healthy",
        "organization_identity": "/api/identity/health",
        "commit": "abcdef012345",
    }
    assert list(resp.json().keys()) == [
        "status",
        "organization_identity",
        "commit",
    ]


def test_openapi_still_available(client, dark):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "LOOPER API"

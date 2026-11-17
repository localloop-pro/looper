"""Public API front door for api.localloop.ai (PR A).

Gated by LOOPER_FRONTDOOR_LIVE (default off). When off, GET / is the same
fixed JSON payload as before this module existed. When on, / negotiates
HTML vs JSON from Accept, and /reference, /robots.txt, /llms.txt and
/sitemap.xml become available. /api/* is never negotiated.
"""
from __future__ import annotations

import os
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

# Exact key order of today's public root JSON (frozen for HybridCard / probes).
ROOT_JSON_KEYS = ("name", "version", "status", "docs", "organization_identity")

VARY_NEGOTIATED = "Accept, Origin"


def frontdoor_live() -> bool:
    """True only when LOOPER_FRONTDOOR_LIVE is an explicit truthy value."""
    return (os.getenv("LOOPER_FRONTDOOR_LIVE") or "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def root_payload() -> dict[str, str]:
    """Fixed root JSON; insertion order is the public contract."""
    return {
        "name": "LOOPER API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "organization_identity": "/api/identity/domains",
    }


def _parse_accept(header: str) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        pieces = [p.strip() for p in part.split(";")]
        media = pieces[0].lower()
        q = 1.0
        for param in pieces[1:]:
            if param.startswith("q="):
                try:
                    q = float(param[2:].strip())
                except ValueError:
                    q = 0.0
        items.append((media, q))
    return items


def _specific_q(items: list[tuple[str, float]], exact: str, type_wild: str) -> float | None:
    """Best q for a media type: exact > type/* > */*. None if no match."""
    exact_q: float | None = None
    type_q: float | None = None
    star_q: float | None = None
    for media, q in items:
        if media == exact:
            exact_q = q if exact_q is None else max(exact_q, q)
        elif media == type_wild:
            type_q = q if type_q is None else max(type_q, q)
        elif media == "*/*":
            star_q = q if star_q is None else max(star_q, q)
    if exact_q is not None:
        return exact_q
    if type_q is not None:
        return type_q
    if star_q is not None:
        return star_q
    return None


def wants_html(accept: str | None) -> bool:
    """True when text/html clearly beats application/json on Accept q-values.

    No Accept, empty Accept, */*, or application/json → JSON (API default).
    Ties prefer JSON so HybridCard and bare curl never get HTML by accident.
    """
    if accept is None or not accept.strip():
        return False
    items = _parse_accept(accept)
    if not items:
        return False
    html_q = _specific_q(items, "text/html", "text/*")
    json_q = _specific_q(items, "application/json", "application/*")
    # Only */* (or other non-html types): stay JSON.
    if html_q is None:
        return False
    if json_q is None:
        return html_q > 0
    return html_q > json_q


def _root_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>LOOPER API</title>
  <style>
    :root { color-scheme: light; --ink:#1a1f16; --muted:#5c664f; --bg:#f3f6ef; --line:#d5ddd0; --accent:#2f5d3a; }
    body { margin:0; font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
      background: radial-gradient(circle at top left,#e7efe0,var(--bg) 45%,#eef2ea);
      color:var(--ink); min-height:100vh; }
    main { max-width:40rem; margin:0 auto; padding:4.5rem 1.25rem 3rem; }
    p.brand { margin:0 0 .75rem; font-size:clamp(2.4rem,6vw,3.4rem); letter-spacing:-.03em; font-weight:700; }
    h1 { margin:0 0 1rem; font-size:1.15rem; font-weight:600; color:var(--muted); }
    p.lead { margin:0 0 1.75rem; line-height:1.5; color:var(--muted); }
    ul { list-style:none; padding:0; margin:0; border-top:1px solid var(--line); }
    li { border-bottom:1px solid var(--line); }
    a { display:block; padding:.85rem 0; color:var(--accent); text-decoration:none; }
    a:hover { text-decoration:underline; }
    code { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:.92em; }
  </style>
</head>
<body>
  <main>
    <p class="brand">LOOPER API</p>
    <h1>LocalLoop community connection agent</h1>
    <p class="lead">JSON by default. Browse the human reference when you want HTML docs.</p>
    <ul>
      <li><a href="/reference">API reference</a></li>
      <li><a href="/openapi.json"><code>/openapi.json</code></a></li>
      <li><a href="/health"><code>/health</code></a></li>
      <li><a href="/api/identity/domains"><code>/api/identity/domains</code></a></li>
      <li><a href="/llms.txt"><code>/llms.txt</code></a></li>
    </ul>
  </main>
</body>
</html>
"""


def _reference_html() -> str:
    # Scalar loads openapi.json from this origin; no server-side template deps.
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>LOOPER API reference</title>
  <style>body{margin:0}</style>
</head>
<body>
  <script id="api-reference" data-url="/openapi.json"></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
"""


def _robots_txt() -> str:
    return """User-agent: *
Allow: /
Allow: /reference
Allow: /docs
Allow: /openapi.json
Allow: /health
Allow: /llms.txt
Allow: /sitemap.xml
Disallow: /api/
"""


def _llms_txt() -> str:
    return """# LOOPER API

> LocalLoop community connection agent — search, discover, and organization identity.

This API is JSON-first. Partners should call /api/* with application/json (or no Accept).

## Endpoints

- GET / — service descriptor (JSON by default; HTML when Accept prefers text/html)
- GET /health — liveness + deployed commit
- GET /reference — human API reference (OpenAPI via Scalar)
- GET /openapi.json — OpenAPI schema
- GET /api/search — review-backed business search
- GET /api/discover — suburb discover
- GET /api/identity/domains — organization Kaspa identity records

## Notes

- Never rank by payment or discount; results are review / recency / proximity only.
- Bridge ingest and write paths require signed headers; public writes stay locked.
"""


def _sitemap_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://api.localloop.ai/</loc></url>
  <url><loc>https://api.localloop.ai/reference</loc></url>
  <url><loc>https://api.localloop.ai/docs</loc></url>
  <url><loc>https://api.localloop.ai/openapi.json</loc></url>
  <url><loc>https://api.localloop.ai/health</loc></url>
  <url><loc>https://api.localloop.ai/llms.txt</loc></url>
  <url><loc>https://api.localloop.ai/robots.txt</loc></url>
</urlset>
"""


def json_root_response(*, negotiate: bool) -> JSONResponse:
    headers = {"Vary": VARY_NEGOTIATED} if negotiate else None
    return JSONResponse(content=root_payload(), headers=headers)


def html_root_response() -> HTMLResponse:
    return HTMLResponse(content=_root_html(), headers={"Vary": VARY_NEGOTIATED})


def register_public_surface(app: FastAPI) -> None:
    """Attach front-door routes. Call once after the FastAPI app is created.

    Takes over /docs (swagger when dark; 301 → /reference when live). openapi.json
    stays on FastAPI's default path.
    """

    @app.get("/")
    @app.head("/", include_in_schema=False)
    def root(request: Request):
        live = frontdoor_live()
        if live and wants_html(request.headers.get("accept")):
            return html_root_response()
        return json_root_response(negotiate=live)

    @app.get("/docs", include_in_schema=False)
    @app.head("/docs", include_in_schema=False)
    def docs():
        if frontdoor_live():
            return RedirectResponse(url="/reference", status_code=301)
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Swagger UI",
        )

    @app.get("/reference", include_in_schema=False)
    @app.head("/reference", include_in_schema=False)
    def reference():
        if not frontdoor_live():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return HTMLResponse(content=_reference_html(), headers={"Vary": VARY_NEGOTIATED})

    @app.get("/robots.txt", include_in_schema=False)
    @app.head("/robots.txt", include_in_schema=False)
    def robots():
        if not frontdoor_live():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return PlainTextResponse(content=_robots_txt(), media_type="text/plain")

    @app.get("/llms.txt", include_in_schema=False)
    @app.head("/llms.txt", include_in_schema=False)
    def llms():
        if not frontdoor_live():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return PlainTextResponse(content=_llms_txt(), media_type="text/plain")

    @app.get("/sitemap.xml", include_in_schema=False)
    @app.head("/sitemap.xml", include_in_schema=False)
    def sitemap():
        if not frontdoor_live():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return Response(content=_sitemap_xml(), media_type="application/xml")

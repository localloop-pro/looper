"""LOOPER Backend API — FastAPI Application"""
import os
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from models import init_db
from services.correlation import CorrelationMiddleware
from services.edge_boundary import PublicReadBoundary
from routes import users, search, map, reviews, ingest, discover, identity

# Initialize DB tables
init_db()

app = FastAPI(
    title="LOOPER API",
    description="LocalLoop community connection agent. Connects people with businesses and services.",
    version="0.1.0",
)

# Public read boundary (issue #8): request id, opt-in per-IP read rate limit
# and opt-in short-TTL cache for search/discover/businesses. Registered BEFORE
# CORS so CORS stays outermost and HIT/429/STALE answers keep CORS headers.
app.add_middleware(PublicReadBoundary)

# CORS — every live host that embeds the Jarvis dock or Looper widget.
# localloop.ai serves the map (Jarvis dock calls api.localloop.ai from the
# browser); hybridcard.ai embeds the read-only search widget.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://localloop.ai",
        "https://www.localloop.ai",
        "https://localloop.pro",
        "https://www.localloop.pro",
        "https://explorer.localloop.ai",
        "https://hybridcard.ai",
        "https://www.hybridcard.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Looper-Cache", "Retry-After"],
)

# E6 correlation (issue #9): canonical X-Request-ID + one PII-free JSON trace
# line per request. Added LAST so it is the outermost layer and also covers
# CORS rejections and the read boundary's HIT/STALE/429 answers. It rewrites
# the inbound id first, so PublicReadBoundary echoes the same canonical id.
# LOOPER_TRACE_LOG=off silences the log lines (the header echo stays).
app.add_middleware(CorrelationMiddleware)

# Register routes
app.include_router(users.router)
app.include_router(search.router)
app.include_router(map.router)
app.include_router(reviews.router)
app.include_router(ingest.router)
app.include_router(discover.router)
app.include_router(identity.router)

# Serve the embeddable web layer (widget + Jarvis map demo) same-origin so
# the demo needs zero CORS/config: http://localhost:8000/demo
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.exists():
    DEMO_DEEP_LINK_PARAMS = ("cat", "q", "fly")
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    @app.get("/demo", include_in_schema=False)
    def jarvis_demo(request: Request):
        # Forward ONLY the F4.2 deep-link params (cat, q, fly), first value
        # of each, re-encoded by us. Everything else (api=, next=, ...) is
        # dropped, and the path is fixed, so input can never pick the host
        # or point the page at another API (looper#70).
        # A blank first value still claims its key (?q=&q=x forwards no q):
        # the page reads the first value only, so a later one must not win.
        seen, kept = set(), {}
        for key, value in parse_qsl(request.url.query, keep_blank_values=True):
            if key in DEMO_DEEP_LINK_PARAMS and key not in seen:
                seen.add(key)
                if value:
                    kept[key] = value
        target = "/web/jarvis/demo-map.html"
        if kept:
            target += "?" + urlencode(kept, quote_via=quote, safe=",")
        return RedirectResponse(target)


@app.get("/")
def root():
    return {
        "name": "LOOPER API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "organization_identity": "/api/identity/domains",
    }


def deployed_commit():
    """Short commit baked in at build time (looper#86), or "" when unknown.

    LOOPER_COMMIT comes from the Dockerfile's SOURCE_COMMIT build arg; Coolify
    also sets SOURCE_COMMIT at runtime, so it is the fallback. Only a hex sha
    is echoed. Never reads .git or runs git at request time.
    """
    raw = os.getenv("LOOPER_COMMIT", "").strip() or os.getenv("SOURCE_COMMIT", "").strip()
    sha = raw[:12].lower()
    return sha if sha and all(c in "0123456789abcdef" for c in sha) else ""


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "organization_identity": "/api/identity/health",
        "commit": deployed_commit(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("LOOPER_PORT", "8000"))
    # access_log=False: uvicorn's access line logs client IP + raw query text;
    # the PII-free trace record from services/correlation.py replaces it.
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, access_log=False)

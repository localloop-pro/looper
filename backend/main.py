"""LOOPER Backend API — FastAPI Application"""
import os
from pathlib import Path
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
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    @app.get("/demo", include_in_schema=False)
    def jarvis_demo(request: Request):
        # Carry ONLY the query string (F4.2 deep links: ?cat=&q=&fly=) — the
        # path is fixed, so input can never redirect off-site (looper#70).
        target = "/web/jarvis/demo-map.html"
        if request.url.query:
            target += "?" + request.url.query
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


@app.get("/health")
def health():
    return {"status": "healthy", "organization_identity": "/api/identity/health"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("LOOPER_PORT", "8000"))
    # access_log=False: uvicorn's access line logs client IP + raw query text;
    # the PII-free trace record from services/correlation.py replaces it.
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, access_log=False)

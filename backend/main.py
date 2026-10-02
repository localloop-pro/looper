"""LOOPER Backend API — FastAPI Application"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from models import init_db
from services.correlation import CorrelationMiddleware
from services.cors_policy import cors_options
from services.edge_boundary import PublicReadBoundary
from services.origin_guard import OriginKeyGuard
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

# Origin lock (issue #28): when LOOPER_ORIGIN_KEY is set, only requests that
# carry the Worker's x-looper-origin-key pass (GET /health exempt). Added
# after the read boundary so it sits OUTSIDE it (a rejected caller never
# spends a rate-limit bucket or gets a cached answer) and before CORS and
# correlation so the 403 still gets CORS headers and a request id.
app.add_middleware(OriginKeyGuard)

# CORS — the https hosts that embed the Jarvis dock or Looper widget
# (services/cors_policy.py). localhost only via LOOPER_DEV_ORIGINS; no
# credentials (issue #28).
app.add_middleware(CORSMiddleware, **cors_options())

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
    def jarvis_demo():
        return RedirectResponse("/web/jarvis/demo-map.html")


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

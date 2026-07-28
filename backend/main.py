"""LOOPER Backend API — FastAPI Application"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from models import init_db
from routes import users, search, map, reviews, ingest, discover

# Initialize DB tables
init_db()

app = FastAPI(
    title="LOOPER API",
    description="LocalLoop community connection agent. Connects people with businesses and services.",
    version="0.1.0",
)

# CORS — allow web widget and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://localloop.pro",
        "https://www.localloop.pro",
        "https://localloop.ai",
        "https://www.localloop.ai",
        "https://explorer.localloop.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(users.router)
app.include_router(search.router)
app.include_router(map.router)
app.include_router(reviews.router)
app.include_router(ingest.router)
app.include_router(discover.router)

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
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("LOOPER_PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
"""Kill switch for the unauthenticated public writes (BLIND-SPOTS §3.6, step 7).

POST /api/reviews, /api/onboard and /api/pins have no auth. Until a verified
path exists they answer 403 unless LOOPER_PUBLIC_WRITES is exactly "true".

Attach per route decorator, never on an APIRouter: those routers also hold
public reads. It is a dependency (not a handler check) so FastAPI runs it
before body validation and an empty body gets 403, not 422.
"""
import os

from fastapi import HTTPException


def public_writes_enabled() -> bool:
    return os.environ.get("LOOPER_PUBLIC_WRITES") == "true"


def require_public_writes() -> None:
    if not public_writes_enabled():
        raise HTTPException(status_code=403, detail="public writes are disabled")

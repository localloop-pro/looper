"""Public read-only organization identity contract."""
from fastapi import APIRouter, HTTPException

from services.kaspa_identity import normalize_domain, verifier

router = APIRouter(prefix="/api/identity", tags=["identity"])


@router.get("/domains")
def list_domains():
    return {"domains": verifier.list_domains()}


@router.get("/domains/{domain}")
def get_domain(domain: str):
    try:
        normalized = normalize_domain(domain)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Organization identity not found") from exc
    return verifier.verify(normalized)


@router.get("/health")
def identity_health():
    return verifier.health()

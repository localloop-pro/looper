"""LOOPER API — BRIDGE-CONTRACT-v1 receivers (HybridCard → Looper).

Contract rules this file lives by:
- HMAC is verified over the RAW body bytes BEFORE any parsing.
- The sender retries ALL non-2xx and replays events — every handler is
  idempotent on eventId and returns 200 only after a durable commit.
- active:false means DEACTIVATE, never delete.
- discount_size / rank_boost are stored/ignored — never ranking inputs.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import BridgeEvent, Business, Deal, get_db
from schemas import HybridCardCardPayload, HybridCardDealPayload
from services import bridge_hmac
from services.bridge_hmac import BridgeAuthError

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


async def _verified_raw_body(request: Request) -> bytes:
    """Read the raw body and verify the X-HC-* HMAC headers over it.
    Raises 401 on any auth failure."""
    raw = await request.body()
    try:
        bridge_hmac.verify(raw, request.headers)
    except BridgeAuthError:
        raise HTTPException(status_code=401, detail="invalid signature")
    return raw


def _record_event_and_commit(db: Session, event_id: str, event_type: str, raw: bytes) -> dict:
    """Append the idempotency ledger row and commit. A lost unique-index race
    (concurrent replay of the same eventId) is a success, not an error."""
    db.add(BridgeEvent(event_id=event_id, event_type=event_type,
                       payload=raw.decode("utf-8", "replace")))
    try:
        db.commit()  # 200 ONLY after durable commit
    except IntegrityError:
        db.rollback()
        return {"ok": True, "duplicate": True}
    return {"ok": True, "duplicate": False}


def _upsert_business(db: Session, *, hybrid_card_id: str, name: str, category: str,
                     lat: float | None, lng: float | None,
                     website: str | None) -> Business:
    """Create or update the Business keyed on hybrid_card_id (the bridge key)."""
    biz = db.query(Business).filter(Business.hybrid_card_id == hybrid_card_id).first()
    if biz is None:
        biz = Business(hybrid_card_id=hybrid_card_id, source="hybrid_card",
                       name=name, category=category, lat=lat, lng=lng,
                       website=website, is_active=True)
        db.add(biz)
        db.flush()  # need biz.id for FKs before commit
    else:
        biz.name = name
        biz.category = category
        if lat is not None:
            biz.lat = lat
        if lng is not None:
            biz.lng = lng
        if website:
            biz.website = website
    return biz


@router.post("/hybridcard-deal")
async def ingest_hybridcard_deal(request: Request, db: Session = Depends(get_db)):
    """Receiver for LooperIngestPayload (deal.upserted / deal.removed)."""
    raw = await _verified_raw_body(request)
    try:
        payload = HybridCardDealPayload.model_validate_json(raw)
    except ValidationError:
        # non-2xx → sender retries then dead-letters; the designed outcome
        # for permanently malformed payloads.
        raise HTTPException(status_code=422, detail="invalid payload")

    if db.query(BridgeEvent).filter(BridgeEvent.event_id == payload.eventId).first():
        return {"ok": True, "duplicate": True}

    biz = _upsert_business(db, hybrid_card_id=payload.hybrid_card_id,
                           name=payload.business_name, category=payload.category,
                           lat=payload.lat, lng=payload.lng,
                           website=payload.public_card_url)

    deal = db.query(Deal).filter(Deal.deal_id == payload.deal_id).first()
    if deal is None:
        deal = Deal(deal_id=payload.deal_id, business_id=biz.id)
        db.add(deal)
    deal.title = payload.title
    deal.short_description = payload.short_description
    deal.category = payload.category
    deal.pin_type = payload.pin_type
    deal.sub_type = payload.sub_type
    deal.discount_size = payload.discount_size
    deal.lat = payload.lat
    deal.lng = payload.lng
    deal.hours = payload.hours
    deal.public_card_url = payload.public_card_url
    deal.active = payload.active  # deal.removed => False; row kept forever

    event_type = "deal.upserted" if payload.active else "deal.removed"
    return _record_event_and_commit(db, payload.eventId, event_type, raw)


@router.post("/hybridcard-card")
async def ingest_hybridcard_card(request: Request, db: Session = Depends(get_db)):
    """Receiver for card-lifecycle events (card.upserted / card.removed).

    card.removed flips the business is_active flag — its deals stay
    untouched (card unpublish ≠ deal.removed) but the whole business
    disappears from /api/search via the is_active filter.
    """
    raw = await _verified_raw_body(request)
    try:
        payload = HybridCardCardPayload.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(status_code=422, detail="invalid payload")

    if db.query(BridgeEvent).filter(BridgeEvent.event_id == payload.eventId).first():
        return {"ok": True, "duplicate": True}

    biz = _upsert_business(db, hybrid_card_id=payload.hybrid_card_id,
                           name=payload.business_name, category=payload.category,
                           lat=payload.lat, lng=payload.lng,
                           website=payload.public_card_url)
    biz.is_active = payload.active  # is_verified untouched

    event_type = "card.upserted" if payload.active else "card.removed"
    return _record_event_and_commit(db, payload.eventId, event_type, raw)

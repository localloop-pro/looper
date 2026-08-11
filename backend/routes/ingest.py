"""LOOPER API — BRIDGE-CONTRACT-v1 receivers (HybridCard → Looper).

Contract rules this file lives by:
- HMAC is verified over the RAW body bytes BEFORE any parsing.
- The sender retries ALL non-2xx and replays events — every handler is
  idempotent on eventId and returns 200 only after a durable commit.
- Retries arrive OUT OF ORDER (each retry is re-signed with a fresh
  timestamp): the sender's payload updated_at is the ordering key, so a
  stale retry never overwrites newer state (it is recorded + 200'd, but
  its field changes are skipped).
- active:false means DEACTIVATE, never delete.
- discount_size / rank_boost are stored/ignored — never ranking inputs.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import BridgeEvent, Business, Deal, get_db
from schemas import HybridCardCardPayload, HybridCardDealPayload
from services import bridge_hmac
from services.bridge_hmac import BridgeAuthError

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _brain_sync(
    hybrid_card_id: str,
    name: str,
    category: str,
    lat: float | None,
    lng: float | None,
    is_active: bool,
    archetype_id: str | None = None,
    sub_type: str | None = None,
    skip_archetype: bool = False,
    slug: str | None = None,
) -> None:
    """Fire-and-forget TypeDB sync (F2.2).  Never raises.

    Accepts scalar values extracted from the Business ORM object before the
    request session closes — avoids DetachedInstanceError when FastAPI runs
    background tasks after the response is sent.

    slug: sender-supplied stable slug (card payload only; deal payloads omit it).
    skip_archetype=True: preserve existing archetype_id/sub_type in TypeDB
    (used by deal events which carry sub_type but not the card-level archetype).
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "brain"))
        from sync import sync_business  # type: ignore[import]
        sync_business(
            hybrid_card_id=hybrid_card_id,
            name=name,
            category=category,
            lat=lat,
            lng=lng,
            is_active=is_active,
            archetype_id=archetype_id,
            sub_type=sub_type,
            slug=slug,
            skip_archetype=skip_archetype,
        )
    except Exception:
        pass  # additive: TypeDB never blocks ingest

# Real contract payloads are ~2 KB; cap well above that but far below
# anything that could hurt (body is buffered pre-auth and stored in
# bridge_events.payload).
MAX_BODY_BYTES = 64 * 1024


async def _verified_raw_body(request: Request) -> bytes:
    """Read the raw body (bounded) and verify the X-HC-* HMAC headers over it.
    Raises 413 on oversized bodies, 401 on any auth failure."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="payload too large")
    raw = bytes(buf)
    try:
        bridge_hmac.verify(raw, request.headers)
    except BridgeAuthError:
        raise HTTPException(status_code=401, detail="invalid signature")
    return raw


def _parse_sender_ts(value: str | None) -> datetime | None:
    """Sender updated_at (ISO-8601, e.g. 2026-07-11T00:00:00.000Z) → naive UTC.
    Unparseable/missing → None (event applies unconditionally)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _record_event_and_commit(db: Session, event_id: str, event_type: str, raw: bytes,
                             *, stale: bool = False) -> dict:
    """Append the idempotency ledger row and commit. 200 ONLY after the
    commit is durable."""
    db.add(BridgeEvent(event_id=event_id, event_type=event_type,
                       status="stale_skipped" if stale else "processed",
                       payload=raw.decode("utf-8", "replace")))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Only a genuine eventId replay race counts as duplicate — any other
        # integrity failure must stay non-2xx so the sender retries.
        if db.query(BridgeEvent).filter(BridgeEvent.event_id == event_id).first():
            return {"ok": True, "duplicate": True}
        raise HTTPException(status_code=500, detail="transient conflict, retry")
    result = {"ok": True, "duplicate": False}
    if stale:
        result["stale"] = True
    return result


def _upsert_business(db: Session, *, hybrid_card_id: str, name: str, category: str,
                     lat: float | None, lng: float | None, website: str | None,
                     sender_ts: datetime | None) -> tuple[Business, bool]:
    """Create or update the Business keyed on hybrid_card_id (the bridge key).

    Returns (business, stale) — stale=True means a newer bridge event already
    wrote this business, so this event's field changes were skipped."""
    biz = db.query(Business).filter(Business.hybrid_card_id == hybrid_card_id).first()
    if biz is None:
        biz = Business(hybrid_card_id=hybrid_card_id, source="hybrid_card",
                       name=name, category=category, lat=lat, lng=lng,
                       website=website, is_active=True, bridge_updated_at=sender_ts)
        db.add(biz)
        db.flush()  # need biz.id for FKs before commit
        return biz, False
    if sender_ts and biz.bridge_updated_at and sender_ts < biz.bridge_updated_at:
        return biz, True
    biz.name = name
    biz.category = category
    if lat is not None:
        biz.lat = lat
    if lng is not None:
        biz.lng = lng
    if website:
        biz.website = website
    if sender_ts:
        biz.bridge_updated_at = sender_ts
    return biz, False


@router.post("/hybridcard-deal")
async def ingest_hybridcard_deal(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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

    sender_ts = _parse_sender_ts(payload.updated_at)
    biz, _ = _upsert_business(db, hybrid_card_id=payload.hybrid_card_id,
                              name=payload.business_name, category=payload.category,
                              lat=payload.lat, lng=payload.lng,
                              website=payload.public_card_url, sender_ts=sender_ts)

    deal = db.query(Deal).filter(Deal.deal_id == payload.deal_id).first()
    stale = (deal is not None and sender_ts is not None
             and deal.source_updated_at is not None
             and sender_ts < deal.source_updated_at)
    if deal is None:
        deal = Deal(deal_id=payload.deal_id, business_id=biz.id)
        db.add(deal)
    if not stale:
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
        if sender_ts:
            deal.source_updated_at = sender_ts

    event_type = "deal.upserted" if payload.active else "deal.removed"
    result = _record_event_and_commit(db, payload.eventId, event_type, raw, stale=stale)
    if not result.get("duplicate") and not stale:
        # Extract scalars while session is open; background task runs after session closes.
        # skip_archetype=True: deal events carry sub_type but not the card-level archetype;
        # preserving the archetype set by the prior card.upserted event prevents a deal
        # update from replacing a card-supplied classifier with the category fallback.
        background_tasks.add_task(
            _brain_sync,
            biz.hybrid_card_id, biz.name or "", biz.category or "other",
            biz.lat, biz.lng, bool(biz.is_active),
            None, payload.sub_type, True,
        )
    return result


@router.post("/hybridcard-card")
async def ingest_hybridcard_card(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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

    sender_ts = _parse_sender_ts(payload.updated_at)
    biz, stale = _upsert_business(db, hybrid_card_id=payload.hybrid_card_id,
                                  name=payload.business_name, category=payload.category,
                                  lat=payload.lat, lng=payload.lng,
                                  website=payload.public_card_url, sender_ts=sender_ts)
    if not stale:
        biz.is_active = payload.active  # is_verified untouched

    event_type = "card.upserted" if payload.active else "card.removed"
    result = _record_event_and_commit(db, payload.eventId, event_type, raw, stale=stale)
    if not result.get("duplicate") and not stale:
        # Extract scalars while session is open; background task runs after session closes.
        # Pass the sender's authoritative slug so TypeDB uses the stable card slug
        # rather than re-deriving it from the business name.
        background_tasks.add_task(
            _brain_sync,
            biz.hybrid_card_id, biz.name or "", biz.category or "other",
            biz.lat, biz.lng, bool(biz.is_active),
            payload.archetype, payload.sub_type, False, payload.slug,
        )
    return result


@router.get("/status")
def ingest_status(db: Session = Depends(get_db)):
    """Read-only bridge cockpit (F4.3): last 20 events + counts by status
    and type. Public-safe — no payload bodies, aggregate counts only."""
    from sqlalchemy import func as sa_func

    recent = (db.query(BridgeEvent)
              .order_by(BridgeEvent.received_at.desc())
              .limit(20).all())
    by_status = dict(db.query(BridgeEvent.status, sa_func.count(BridgeEvent.id))
                     .group_by(BridgeEvent.status).all())
    by_type = dict(db.query(BridgeEvent.event_type, sa_func.count(BridgeEvent.id))
                   .group_by(BridgeEvent.event_type).all())
    active_deals = db.query(sa_func.count(Deal.id)).filter(Deal.active == True).scalar()
    card_businesses = (db.query(sa_func.count(Business.id))
                       .filter(Business.hybrid_card_id.is_not(None)).scalar())

    return {
        "counts": {
            "total_events": sum(by_status.values()),
            "by_status": by_status,
            "by_type": by_type,
            "active_deals": active_deals,
            "card_businesses": card_businesses,
        },
        "recent_events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "status": e.status,
                "received_at": e.received_at.isoformat() if e.received_at else None,
            }
            for e in recent
        ],
    }

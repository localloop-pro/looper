"""LOOPER API — /api/discover (F2.3): graph-powered discovery with a safe
fallback engine.

Until the TypeDB brain (F2.1/F2.2) is deployed, `TYPEDB_ENABLED=false`
routes every request through the transparent SQLite/haversine fallback —
IDENTICAL response shape, plus `"engine": "fallback"` so callers can tell.
When the graph lands, only `_graph_discover` gets an implementation; the
response contract here does not change.

ANTI-BIAS INVARIANT (BRIDGE-CONTRACT-v1 §7): ranking inputs are
review count, review recency, and proximity ONLY — never discount_size,
source, tier, or any paid signal.
"""
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Business, Review, fold_accents, get_db
from routes.search import get_top_review, haversine_km, resolve_card_url
from schemas import SearchResult
from services import telemetry

router = APIRouter(prefix="/api", tags=["discover"])

# Buffer added to radius_km when testing suburb centroids against the search
# radius — prevents false negatives when a suburb centroid sits just outside
# the radius but the actual suburb boundary overlaps it.
_SUBURB_BUFFER_KM = 2.0

# Seed geography: Eastern Suburbs + Byron (mirrors the voice router's
# SUBURBS table in web/jarvis/voice-command-router.js — keep in sync until
# the TypeDB geo hierarchy replaces both, F2.1).
SUBURB_COORDS = {
    "bondi beach": (-33.8908, 151.2743),
    "north bondi": (-33.8850, 151.2790),
    "bondi junction": (-33.8912, 151.2477),
    "bondi": (-33.8915, 151.2743),
    "tamarama": (-33.8990, 151.2700),
    "bronte": (-33.9036, 151.2630),
    "clovelly": (-33.9120, 151.2610),
    "coogee": (-33.9200, 151.2550),
    "randwick": (-33.9140, 151.2410),
    "maroubra": (-33.9500, 151.2380),
    "rose bay": (-33.8710, 151.2670),
    "double bay": (-33.8770, 151.2430),
    "vaucluse": (-33.8560, 151.2780),
    "dover heights": (-33.8700, 151.2810),
    "waverley": (-33.8980, 151.2540),
    "woollahra": (-33.8870, 151.2410),
    "paddington": (-33.8840, 151.2260),
    "surry hills": (-33.8880, 151.2100),
    "redfern": (-33.8930, 151.2040),
    "alexandria": (-33.9130, 151.1960),
    "byron bay": (-28.6474, 153.6120),
}


def _graph_discover(db, suburb, lat, lng, radius_km, category, limit,
                    intent=None, session_id=None):
    """TypeDB graph engine for /api/discover (F2.3).

    Merges carded businesses from the TypeDB graph with non-carded businesses
    from SQLite so graph discovery maintains parity with the fallback engine.
    Raises on TypeDB connection/query error — caller falls back transparently.
    """
    import os as _os
    from typedb.driver import TypeDB, SessionType, TransactionType  # type: ignore[import]

    address = _os.getenv("TYPEDB_ADDRESS", "localhost:1729")
    typedb_db = _os.getenv("TYPEDB_DB", "localloop")

    # Resolve center (same logic as fallback)
    center = None
    suburb_key = None
    if suburb:
        folded = fold_accents(suburb)
        for key in sorted(SUBURB_COORDS, key=len, reverse=True):
            if key == folded or key in folded:
                suburb_key = key
                center = SUBURB_COORDS[key]
                break
    if center is None and lat is not None and lng is not None:
        center = (lat, lng)
    if center is None:
        raise ValueError("no center to search from")

    center_lat, center_lng = center

    # Suburbs within radius_km + buffer (centroid-based; buffer prevents false
    # negatives when the centroid is just outside the radius but the suburb
    # boundary overlaps).
    nearby_suburbs: set[str] = {
        name for name, (slat, slng) in SUBURB_COORDS.items()
        if haversine_km(center_lat, center_lng, slat, slng) <= radius_km + _SUBURB_BUFFER_KM
    }

    # TypeDB: get active carded business_entities + their suburb name.
    # Raises on connection/query errors → caller falls back to SQLite.
    hybrid_card_ids: set[str] = set()
    with TypeDB.core_driver(address) as driver:
        with driver.session(typedb_db, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                typeql = (
                    "match "
                    "$b isa business_entity, has hybrid_card_id $hid, has is_active true; "
                    "(contained: $b, container: $s) isa located_in; "
                    "$s isa suburb, has name $sname; "
                    "get $b, $hid, $sname;"
                )
                for cm in tx.query.get(typeql):
                    try:
                        hid = cm.get("hid").get_value()
                        sname = cm.get("sname").get_value()
                    except AttributeError:
                        hid = cm.get("hid").value
                        sname = cm.get("sname").value
                    if sname.lower() in nearby_suburbs:
                        hybrid_card_ids.add(hid)

    # Hydrate carded businesses from SQLite (source of truth for full details)
    card_bizs = (
        db.query(Business)
        .filter(
            Business.hybrid_card_id.in_(list(hybrid_card_ids)),
            Business.is_active.is_not(False),
        )
        .all()
    ) if hybrid_card_ids else []

    # Also include non-carded businesses (Facebook-imported, seeded, etc.) so
    # graph discovery maintains parity with the SQLite fallback.
    non_card_bizs = (
        db.query(Business)
        .filter(
            Business.hybrid_card_id.is_(None),
            Business.is_active.is_not(False),
        )
        .all()
    )

    # Carded businesses that have no `located_in` in TypeDB (not yet synced)
    # would be silently dropped by the TypeQL query; include them via SQLite.
    card_biz_ids_in_graph = {b.hybrid_card_id for b in card_bizs}
    extra_carded = [
        b for b in (
            db.query(Business)
            .filter(
                Business.hybrid_card_id.is_not(None),
                Business.is_active.is_not(False),
            )
            .all()
        )
        if b.hybrid_card_id not in card_biz_ids_in_graph
    ]

    businesses = list(card_bizs) + non_card_bizs + extra_carded
    businesses.sort(key=lambda b: b.id)  # neutral, deterministic order before scoring so source is never a tie-breaker

    # Category filter (Python-side; avoids TypeQL string-match quirks)
    if category:
        cat_pat = fold_accents(category).lower()
        businesses = [
            b for b in businesses
            if b.category and cat_pat in fold_accents(b.category).lower()
        ]

    scored = []
    for biz in businesses:
        distance = None
        if biz.lat is not None and biz.lng is not None:
            distance = haversine_km(center_lat, center_lng, biz.lat, biz.lng)
            if distance > radius_km:
                continue
        # no coords: include without distance (sorts last); matches SQLite-path behaviour

        review_count = db.query(func.count(Review.id)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()
        avg_rating = db.query(func.avg(Review.rating)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()
        latest_review_at = db.query(func.max(Review.created_at)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        scored.append({
            "biz": biz,
            "review_count": review_count,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "latest_review_at": latest_review_at,
            "distance_km": round(distance, 1) if distance is not None else None,
        })

    # Anti-bias: reviews DESC → recency DESC → proximity ASC (ONLY ranking inputs)
    scored.sort(key=lambda r: (
        -r["review_count"],
        -(r["latest_review_at"].timestamp() if r["latest_review_at"] else 0),
        r["distance_km"] if r["distance_km"] is not None else 999,
    ))

    results = []
    for r in scored[:limit]:
        biz = r["biz"]
        results.append(SearchResult(
            business_id=biz.id,
            name=biz.name,
            category=biz.category,
            address=biz.address,
            lat=biz.lat,
            lng=biz.lng,
            review_count=r["review_count"],
            avg_rating=r["avg_rating"],
            top_review=get_top_review(biz.id, db),
            distance_km=r["distance_km"],
            website=biz.website,
            card_url=resolve_card_url(biz, db),
        ))

    where = suburb_key or suburb or "this area"
    if not results:
        message = (
            f"Nothing on the loop for {category or 'that'} around {where} yet "
            f"— want to add the first?"
        )
    else:
        message = (
            f"{len(results)} option{'s' if len(results) != 1 else ''} around {where}, "
            f"ranked by community experience. I don't pick favourites — you decide!"
        )

    telemetry.log_query(db, f"discover suburb={suburb or ''} category={category or ''}",
                        intent=intent or "discover", session_id=session_id,
                        response_text=message)

    return {
        "engine": "graph",
        "suburb": suburb_key or suburb,
        "category": category,
        "radius_km": radius_km,
        "results": results,
        "total_results": len(scored),
        "message": message,
    }


@router.get("/discover")
def discover(
    suburb: str | None = Query(None, description="Suburb name, e.g. Bondi"),
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    radius_km: float = Query(5.0, ge=0.1, le=50.0),
    category: str | None = Query(None, description="Business category, e.g. café"),
    limit: int = Query(10, ge=1, le=50),
    intent: str | None = Query(None, description="Caller-classified intent (telemetry only)"),
    session: str | None = Query(None, description="Anonymous session id (telemetry only)"),
    db: Session = Depends(get_db),
):
    """Discover businesses around a suburb or point. Ranked by community
    reviews, review recency, then proximity — never by payment."""
    engine = "fallback"
    if os.getenv("TYPEDB_ENABLED", "false").lower() == "true":
        try:
            return _graph_discover(db, suburb, lat, lng, radius_km, category, limit,
                                   intent=intent, session_id=session)
        except Exception:
            engine = "fallback"  # graph down → transparent fallback (additive rule)

    # Resolve a center: known suburb name beats raw coords.
    center = None
    suburb_key = None
    if suburb:
        folded = fold_accents(suburb)
        for key in sorted(SUBURB_COORDS, key=len, reverse=True):
            if key == folded or key in folded:
                suburb_key = key
                center = SUBURB_COORDS[key]
                break
    if center is None and lat is not None and lng is not None:
        center = (lat, lng)

    query = db.query(Business).filter(Business.is_active.is_not(False))
    if category:
        pattern = f"%{fold_accents(category)}%"
        query = query.filter(func.fold_accents(Business.category).like(pattern))
    if suburb and center is None:
        # unknown suburb: fall back to name-matching the businesses' suburb
        query = query.filter(func.fold_accents(Business.suburb).like(f"%{fold_accents(suburb)}%"))

    scored = []
    for biz in query.all():
        distance = None
        if center and biz.lat is not None and biz.lng is not None:
            distance = haversine_km(center[0], center[1], biz.lat, biz.lng)
            if distance > radius_km:
                continue

        review_count = db.query(func.count(Review.id)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()
        avg_rating = db.query(func.avg(Review.rating)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()
        latest_review_at = db.query(func.max(Review.created_at)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        scored.append({
            "biz": biz,
            "review_count": review_count,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "latest_review_at": latest_review_at,
            "distance_km": round(distance, 1) if distance is not None else None,
        })

    # reviews DESC → recency DESC → proximity ASC (the ONLY ranking inputs)
    scored.sort(key=lambda r: (
        -r["review_count"],
        -(r["latest_review_at"].timestamp() if r["latest_review_at"] else 0),
        r["distance_km"] if r["distance_km"] is not None else 999,
    ))

    results = []
    for r in scored[:limit]:
        biz = r["biz"]
        results.append(SearchResult(
            business_id=biz.id,
            name=biz.name,
            category=biz.category,
            address=biz.address,
            lat=biz.lat,
            lng=biz.lng,
            review_count=r["review_count"],
            avg_rating=r["avg_rating"],
            top_review=get_top_review(biz.id, db),
            distance_km=r["distance_km"],
            website=biz.website,
            # Pass-through stored URL (localhost /c/{slug} or *.hybridcard.ai) — never rewrite.
            card_url=resolve_card_url(biz, db),
        ))

    where = suburb_key or suburb or "this area"
    if not results:
        message = f"Nothing on the loop for {category or 'that'} around {where} yet — want to add the first?"
    else:
        message = (f"{len(results)} option{'s' if len(results) != 1 else ''} around {where}, "
                   f"ranked by community experience. I don't pick favourites — you decide!")

    telemetry.log_query(db, f"discover suburb={suburb or ''} category={category or ''}",
                        intent=intent or "discover", session_id=session,
                        response_text=message)

    return {
        "engine": engine,
        "suburb": suburb_key or suburb,
        "category": category,
        "radius_km": radius_km,
        "results": results,
        "total_results": len(scored),
        "message": message,
    }

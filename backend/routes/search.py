"""LOOPER API — Search Routes — Neutral, review-backed business discovery"""
import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Business, Deal, Review, fold_accents, get_db
from schemas import SearchResponse, SearchResult
from services import telemetry

router = APIRouter(prefix="/api", tags=["search"])


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two lat/lng points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_top_review(business_id: int, db: Session) -> str | None:
    """Get the most recent public review for a business."""
    review = (db.query(Review)
              .filter(Review.business_id == business_id, Review.is_public == True)
              .order_by(Review.created_at.desc())
              .first())
    if review and review.review_text:
        excerpt = review.review_text[:150]
        if len(review.review_text) > 150:
            excerpt += "..."
        return f'"{excerpt}"'
    return None


def resolve_card_url(biz: Business, db: Session) -> str | None:
    """Pass-through HybridCard public URL for "View card →" (never a ranking input).

    Prefer an active deal's public_card_url, else the business website set by
    bridge ingest (which IS public_card_url). Accept any host — prod
    ``*.hybridcard.ai`` and local/dev ``http://localhost:3000/c/{slug}`` alike.
    Never rebuild from slug and never rewrite the stored URL.
    """
    if not biz.hybrid_card_id:
        return None
    deal = (db.query(Deal)
            .filter(Deal.business_id == biz.id,
                    Deal.active == True,
                    Deal.public_card_url.is_not(None))
            .first())
    if deal and deal.public_card_url:
        return deal.public_card_url
    if biz.website:
        return biz.website
    return None


@router.get("/search", response_model=SearchResponse)
def search_businesses(
    q: str = Query(..., min_length=1, description="Search query"),
    lat: float | None = Query(None, description="User latitude"),
    lng: float | None = Query(None, description="User longitude"),
    radius_km: float = Query(5.0, ge=0.1, le=5000.0),
    category: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
    intent: str | None = Query(None, description="Caller-classified intent (telemetry only, never ranking)"),
    session: str | None = Query(None, description="Anonymous session id (telemetry only)"),
    db: Session = Depends(get_db),
):
    """Search businesses by name, category, or description. Ranked by verifiable data ONLY:
    1. Review count (more reviews = more community trust)
    2. Recency of reviews
    3. Proximity (if location provided)
    NEVER ranks by sponsorship, payment, or editor preference."""

    # Build query — deactivated businesses (card.removed) never surface.
    # IS NOT false (not != false): NULL-safe, so legacy NULL rows stay visible
    query = db.query(Business).filter(Business.is_active.is_not(False))
    if category:
        query = query.filter(Business.category == category)

    # Tokenized free-text search — split query into words, match any token
    # This way "café near Bondi Beach" matches businesses with category "café" in "Bondi"
    # Tokens are accent-folded ("cafe" == "café") — voice transcripts type ASCII.
    tokens = [fold_accents(t.strip()) for t in q.split() if len(t.strip()) > 1]
    # Also include stopwords that might be relevant (like "beach", "road")
    stopwords = {"near", "the", "a", "an", "in", "at", "on", "is", "are", "was", "for", "to", "of", "and", "or", "i", "me", "my", "what", "where", "who", "how", "find", "good", "best", "great"}
    search_tokens = [t for t in tokens if t not in stopwords]
    
    if not search_tokens:
        search_tokens = tokens  # fallback if all words are stopwords
    
    # Build OR filter: match any token against name, category, suburb,
    # description — both sides accent-folded via the registered SQLite
    # fold_accents() function (models.py), so "cafe" finds "café".
    from sqlalchemy import or_
    conditions = []
    for token in search_tokens:
        pattern = f"%{token}%"
        conditions.append(func.fold_accents(Business.name).like(pattern))
        conditions.append(func.fold_accents(Business.category).like(pattern))
        conditions.append(func.fold_accents(Business.suburb).like(pattern))
        conditions.append(func.fold_accents(Business.description).like(pattern))

    query = query.filter(or_(*conditions))

    businesses = query.all()

    # Score and rank by review count + recency (verifiable data only)
    results = []
    for biz in businesses:
        review_count = db.query(func.count(Review.id)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        avg_rating = db.query(func.avg(Review.rating)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        # Distance if coords available
        distance = None
        if lat is not None and lng is not None and biz.lat and biz.lng:
            distance = haversine_km(lat, lng, biz.lat, biz.lng)
            if distance > radius_km:
                continue  # outside search radius

        top_review = get_top_review(biz.id, db)

        # Relevance score: boost category/name matches over generic suburb
        # matches (accent-folded on both sides, same as the SQL filter)
        relevance = 0
        for token in search_tokens:
            if token in (fold_accents(biz.category) or ""):
                relevance += 5  # category match = highest relevance
            if token in (fold_accents(biz.name) or ""):
                relevance += 3  # name match
            if biz.suburb and token in fold_accents(biz.suburb):
                relevance += 2  # suburb match
            if biz.description and token in fold_accents(biz.description):
                relevance += 1

        results.append({
            "business": biz,
            "review_count": review_count,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
            "top_review": top_review,
            "distance_km": round(distance, 1) if distance else None,
            "relevance": relevance,
        })

    # SORT: relevance DESC (category match > name match > suburb match),
    # then review_count DESC (most community-trusted first), then proximity
    # ANTI-BIAS INVARIANT (BRIDGE-CONTRACT-v1 §7): ranking inputs are
    # relevance, review_count, distance ONLY. Never discount_size, source,
    # rank_boost, or any paid signal. test_search_antibias.py enforces this.
    results.sort(key=lambda r: (-r["relevance"], -r["review_count"], r["distance_km"] or 999))

    # Build response
    ranked = []
    for r in results[:limit]:
        biz = r["business"]
        # HybridCard connection: informational link only — NEVER a ranking input (§7).
        ranked.append(SearchResult(
            business_id=biz.id,
            name=biz.name,
            category=biz.category,
            address=biz.address,
            lat=biz.lat,
            lng=biz.lng,
            review_count=r["review_count"],
            avg_rating=r["avg_rating"],
            top_review=r["top_review"],
            distance_km=r["distance_km"],
            website=biz.website,
            card_url=resolve_card_url(biz, db),
        ))

    # Contextual message from LOOPER (neutral, informative)
    if not ranked:
        message = (
            f"I couldn't find any {category or ''} businesses matching '{q}' "
            f"in this area yet. Want to be the first to add one? 🌱"
        )
    elif len(ranked) == 1:
        message = (
            f"Here's the only {category or ''} match for '{q}' in your area. "
            f"It has {ranked[0].review_count} community review{'s' if ranked[0].review_count != 1 else ''}."
        )
    else:
        message = (
            f"Here are {len(ranked)} {category or ''} options for '{q}', "
            f"ranked by community experience (most reviewed first). "
            f"I don't pick favorites — you decide! ✨"
        )

    # F2.5 telemetry: query + summary into training_log (PII-scrubbed,
    # best-effort — see services/telemetry.py). Feeds training/export.py.
    telemetry.log_query(
        db, q, intent=intent or "search", session_id=session,
        response_text=f"{message} [{', '.join(r.name for r in ranked[:5])}]",
    )

    return SearchResponse(
        query=q,
        results=ranked,
        message=message,
        total_results=len(results),
    )


@router.get("/businesses")
def list_businesses(
    category: str | None = Query(None),
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    radius_km: float = Query(5.0),
    limit: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    """List businesses, optionally filtered by category and location."""
    query = db.query(Business).filter(Business.is_active.is_not(False))
    if category:
        query = query.filter(Business.category == category)

    results = []
    for biz in query.limit(limit).all():
        review_count = db.query(func.count(Review.id)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        distance = None
        if lat and lng and biz.lat and biz.lng:
            distance = haversine_km(lat, lng, biz.lat, biz.lng)
            if distance > radius_km:
                continue

        results.append({
            "id": biz.id,
            "name": biz.name,
            "category": biz.category,
            "address": biz.address,
            "lat": biz.lat,
            "lng": biz.lng,
            "review_count": review_count,
            "distance_km": round(distance, 1) if distance else None,
        })

    results.sort(key=lambda r: (-r["review_count"], r["distance_km"] or 999))
    return {"category": category, "count": len(results), "results": results}
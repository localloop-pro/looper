"""LOOPER API — Search Routes — Neutral, review-backed business discovery"""
import math
import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Business, Deal, Review, fold_accents, get_db
from routes.params import OptionalLatitude, OptionalLongitude, RadiusKm
from schemas import SearchResponse, SearchResult
from services import query_terms, telemetry

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


def _read_fallback_km() -> float:
    """LOOPER_SEARCH_FALLBACK_KM, read once at startup (default 10 km).

    float() accepts "inf", "nan" and overflows like "1e309" (-> inf); an
    infinite radius would return every business and serialize
    widened_to_km as null, so anything not finite and positive is 10."""
    try:
        km = float(os.getenv("LOOPER_SEARCH_FALLBACK_KM", "10"))
    except ValueError:
        return 10.0
    return km if math.isfinite(km) and km > 0 else 10.0


# Widened radius for one retry when nothing matches inside radius_km
# (looper#73). Never smaller than the caller's radius_km.
FALLBACK_KM = _read_fallback_km()

# The order results.sort() below really uses, in words (looper#73, §4.7).
ORDER_TEXT = "best match first, then most community reviews, then nearest"


def _km(value: float) -> str:
    """1.5 -> "1.5", 10.0 -> "10"."""
    return f"{round(value, 1):g}"


@router.get("/search", response_model=SearchResponse)
def search_businesses(
    q: str = Query(..., min_length=1, description="Search query"),
    lat: OptionalLatitude = None,
    lng: OptionalLongitude = None,
    radius_km: float = Query(5.0, ge=0.1, le=5000.0),
    category: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
    intent: str | None = Query(None, description="Caller-classified intent (telemetry only, never ranking)"),
    session: str | None = Query(None, description="Anonymous session id (telemetry only)"),
    db: Session = Depends(get_db),
):
    """Search businesses by name, category, or description. Ranked by verifiable data ONLY:
    1. Relevance (category match > name match > suburb match > description)
    2. Review count (more reviews = more community trust)
    3. Proximity (if location provided)
    NEVER ranks by sponsorship, payment, or editor preference.

    When lat/lng are given and nothing matches inside radius_km, the same
    candidates are filtered once more with FALLBACK_KM and the response sets
    ``widened_to_km`` (looper#73). The sort is identical in both passes."""

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
    
    # Expand each word with the explicit synonym / compound table
    # (services/query_terms.py, looper#29): "hairdresser" also tries "hair"
    # and "salon". Originals always stay; added words must start a word.
    groups = query_terms.expand(search_tokens)

    # Build OR filter: match any term against name, category, suburb,
    # description — both sides accent-folded via the registered SQLite
    # fold_accents() function (models.py), so "cafe" finds "café".
    # SQL LIKE only narrows candidates; group_matches() below is the rule.
    from sqlalchemy import or_
    conditions = []
    for term in sorted({t.text for group in groups for t in group}):
        pattern = f"%{term}%"
        conditions.append(func.fold_accents(Business.name).like(pattern))
        conditions.append(func.fold_accents(Business.category).like(pattern))
        conditions.append(func.fold_accents(Business.suburb).like(pattern))
        conditions.append(func.fold_accents(Business.description).like(pattern))

    query = query.filter(or_(*conditions))

    businesses = query.all()

    # Text-matching candidates with their distance. The radius filter runs
    # on this list, so the widened pass needs no second SQL query.
    candidates = []
    for biz in businesses:
        fields = {
            "category": fold_accents(biz.category),
            "name": fold_accents(biz.name),
            "suburb": fold_accents(biz.suburb),
            "description": fold_accents(biz.description),
        }
        # LIKE is a substring prefilter; drop rows whose only hit is an
        # added alternative in the middle of a word ("hair" in "chair").
        if not any(query_terms.group_matches(g, v) for g in groups for v in fields.values()):
            continue

        # Distance if coords available
        distance = None
        if lat is not None and lng is not None and biz.lat and biz.lng:
            distance = haversine_km(lat, lng, biz.lat, biz.lng)
        candidates.append((biz, fields, distance))

    def within(km: float):
        return [c for c in candidates if c[2] is None or c[2] <= km]

    in_range = within(radius_km)
    widened_to_km = None
    # One widened pass at most: only with a location, only when the first
    # pass is empty, and only if it actually widens.
    if not in_range and lat is not None and lng is not None and FALLBACK_KM > radius_km:
        widened_to_km = FALLBACK_KM
        in_range = within(widened_to_km)

    # Score and rank by review count + recency (verifiable data only)
    results = []
    for biz, fields, distance in in_range:
        review_count = db.query(func.count(Review.id)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        avg_rating = db.query(func.avg(Review.rating)).filter(
            Review.business_id == biz.id, Review.is_public == True
        ).scalar()

        top_review = get_top_review(biz.id, db)

        # Relevance score: boost category/name matches over generic suburb
        # matches (accent-folded on both sides, same as the SQL filter)
        # One score per query word: an expanded word counts once, no matter
        # how many of its alternatives hit.
        relevance = 0
        for group in groups:
            if query_terms.group_matches(group, fields["category"]):
                relevance += 5  # category match = highest relevance
            if query_terms.group_matches(group, fields["name"]):
                relevance += 3  # name match
            if query_terms.group_matches(group, fields["suburb"]):
                relevance += 2  # suburb match
            if query_terms.group_matches(group, fields["description"]):
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

    message = _message(q, category, ranked, radius_km, widened_to_km)

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
        widened_to_km=widened_to_km,
    )


def _message(q: str, category: str | None, ranked: list, radius_km: float,
             widened_to_km: float | None) -> str:
    """Neutral, plain-text answer (the #37 contract: renderers may insert it
    as text). Describes the real sort order and never invites an action
    that needs LOOPER_PUBLIC_WRITES (POST onboard/reviews/pins 403 by default)."""
    kind = f"{category} " if category else ""
    if not ranked:
        where = f"within {_km(widened_to_km)} km" if widened_to_km else "near here"
        return f"No one's listed for '{q}' {where} yet."

    lead = ""
    if widened_to_km:
        nearest = min((r.distance_km for r in ranked if r.distance_km is not None), default=None)
        lead = f"Nothing within {_km(radius_km)} km for '{q}'. "
        if nearest is not None:
            lead += f"The nearest match is {_km(nearest)} km away. "

    if len(ranked) == 1:
        n = ranked[0].review_count
        return (f"{lead}Here's the only {kind}match for '{q}'. "
                f"It has {n} community review{'s' if n != 1 else ''}.")
    return (f"{lead}Here are {len(ranked)} {kind}options for '{q}': "
            f"{ORDER_TEXT}. I don't pick favorites — you decide! ✨")


@router.get("/businesses")
def list_businesses(
    category: str | None = Query(None),
    lat: OptionalLatitude = None,
    lng: OptionalLongitude = None,
    radius_km: RadiusKm = 5.0,
    limit: int = Query(20, ge=1, le=50),
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
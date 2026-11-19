"""LOOPER API — Review Routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Review, Business, User, get_db
from schemas import SubmitReviewRequest
from services.write_guard import require_public_writes

# looper#133: reviewer first names stay in the DB and never leave on a public read.
PUBLIC_REVIEWER_LABEL = "Community member"

router = APIRouter(prefix="/api", tags=["reviews"])


@router.post("/reviews", dependencies=[Depends(require_public_writes)])
def submit_review(req: SubmitReviewRequest, db: Session = Depends(get_db)):
    """Submit a review for a business."""
    # Verify business exists
    business = db.query(Business).filter(Business.id == req.business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Verify user exists
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for duplicate review
    existing = db.query(Review).filter(
        Review.business_id == req.business_id,
        Review.user_id == req.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You've already reviewed this business")

    review = Review(
        business_id=req.business_id,
        user_id=req.user_id,
        rating=req.rating,
        review_text=req.review_text,
        # Never trust the caller: a direct submission is not a verified visit.
        verified_visit=False,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    # Update business rating cache
    avg = db.query(func.avg(Review.rating)).filter(
        Review.business_id == req.business_id
    ).scalar()
    count = db.query(func.count(Review.id)).filter(
        Review.business_id == req.business_id
    ).scalar()

    return {
        "review_id": review.id,
        "business_name": business.name,
        "rating": review.rating,
        "business_avg_rating": round(avg, 1) if avg else None,
        "business_review_count": count,
        "message": f"Thanks for reviewing {business.name}! Your voice helps the community. ⭐",
    }


@router.get("/reviews/{business_id}")
def get_reviews(
    business_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get reviews for a business, most recent first.

    404 for an unknown business, so callers can tell "no such business" from
    "no reviews yet" (a known business with no reviews is 200 + []).
    """
    if not db.query(Business.id).filter(Business.id == business_id).first():
        raise HTTPException(status_code=404, detail="Business not found")

    reviews = (
        db.query(Review)
        .filter(Review.business_id == business_id, Review.is_public == True)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .all()
    )

    avg_rating = db.query(func.avg(Review.rating)).filter(
        Review.business_id == business_id, Review.is_public == True
    ).scalar()
    total = db.query(func.count(Review.id)).filter(
        Review.business_id == business_id, Review.is_public == True
    ).scalar()

    # Public-safe: never publish a member's name (looper#133). Every reviewer
    # gets the same label, so the response shape stays the same.
    return {
        "business_id": business_id,
        "avg_rating": round(avg_rating, 1) if avg_rating else None,
        "total_reviews": total,
        "reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "text": r.review_text,
                "reviewer": PUBLIC_REVIEWER_LABEL,
                "verified_visit": r.verified_visit,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }
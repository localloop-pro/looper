"""LOOPER API — Review Routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Review, Business, User, get_db
from schemas import SubmitReviewRequest

router = APIRouter(prefix="/api", tags=["reviews"])


@router.post("/reviews")
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
        verified_visit=req.verified_visit,
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
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Get reviews for a business, most recent first."""
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

    # Get reviewer names
    user_ids = list(set(r.user_id for r in reviews))
    users = {u.id: u.first_name for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    return {
        "business_id": business_id,
        "avg_rating": round(avg_rating, 1) if avg_rating else None,
        "total_reviews": total,
        "reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "text": r.review_text,
                "reviewer": users.get(r.user_id, "Anonymous"),
                "verified_visit": r.verified_visit,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }
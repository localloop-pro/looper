"""LOOPER API — User Onboarding Routes"""
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import User, get_db
from schemas import OnboardUserRequest, OnboardUserResponse
from services.write_guard import require_public_writes

router = APIRouter(prefix="/api", tags=["users"])


def generate_join_code(db: Session) -> str:
    """Generate a unique 6-digit join code."""
    for _ in range(100):  # max 100 attempts to avoid collision
        code = f"{random.randint(0, 999999):06d}"
        if not db.query(User).filter(User.join_code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique code")


@router.post("/onboard", response_model=OnboardUserResponse,
             dependencies=[Depends(require_public_writes)])
def onboard_user(req: OnboardUserRequest, db: Session = Depends(get_db)):
    """Register a new user and generate their 6-digit join code."""
    # An already-registered number gets 409 with no data. Echoing the stored
    # user_id / join code would hand them to anyone who knows the mobile.
    existing = db.query(User).filter(User.mobile_number == req.mobile_number).first()
    if existing:
        raise HTTPException(status_code=409, detail="could not complete sign-up")

    # Create new user
    join_code = generate_join_code(db)
    user = User(
        first_name=req.first_name,
        mobile_number=req.mobile_number,
        join_code=join_code,
        user_type=req.user_type or "local",
        interest_category=req.interest_category,
        preferred_language=req.preferred_language or "en",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Welcome message based on user_type and interest
    if user.user_type == "tourist":
        message = (
            f"Welcome to Bondi, {user.first_name}! 🧳\n\n"
            f"Your Bondi Local Loop code is: **{join_code}**\n\n"
            f"Here's how it works:\n"
            f"1. Use this code to join the Bondi Local Loop community\n"
            f"2. I can show you local attractions, transport tips, and hidden gems\n"
            f"3. Would you like me to show you what's around on the map? 📍"
        )
    else:
        message = (
            f"Welcome to Bondi Local Loop, {user.first_name}! 🏠\n\n"
            f"Your unique join code is: **{join_code}**\n\n"
            f"What you can do:\n"
            f"1. Use this code to join the Bondi Local Loop group\n"
            f"2. Search for local businesses backed by real reviews\n"
            f"3. Pin your needs or offerings on the community map\n\n"
            f"Would you like me to show you available community needs on the map? 📍"
        )

    return OnboardUserResponse(
        user_id=user.id,
        first_name=user.first_name,
        join_code=join_code,
        message=message,
    )


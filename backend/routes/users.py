"""LOOPER API — User Onboarding Routes"""
import random
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from models import User, get_db
from schemas import OnboardUserRequest, OnboardUserResponse
from services.onboard_sms import deliver_join_code_sms
from services.write_guard import require_public_writes

router = APIRouter(prefix="/api", tags=["users"])

ONBOARD_ACK_MESSAGE = (
    "If this number can sign up, you'll receive your Bondi Local Loop code shortly. "
    "Watch your messages for next steps."
)


def generate_join_code(db: Session) -> str:
    """Generate a unique 6-digit join code."""
    for _ in range(100):  # max 100 attempts to avoid collision
        code = f"{random.randint(0, 999999):06d}"
        if not db.query(User).filter(User.join_code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique code")


def _onboard_ack() -> OnboardUserResponse:
    return OnboardUserResponse(message=ONBOARD_ACK_MESSAGE)


@router.post("/onboard", response_model=OnboardUserResponse,
             dependencies=[Depends(require_public_writes)])
def onboard_user(
    req: OnboardUserRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register a new user; return the same public-safe ack for every mobile."""
    existing = db.query(User).filter(User.mobile_number == req.mobile_number).first()
    # Same join-code probe on both paths so timing is closer for enumerators.
    _unused = generate_join_code(db)

    if not existing:
        user = User(
            first_name=req.first_name,
            mobile_number=req.mobile_number,
            join_code=_unused,
            user_type=req.user_type or "local",
            interest_category=req.interest_category,
            preferred_language=req.preferred_language or "en",
        )
        db.add(user)
        db.commit()

    background_tasks.add_task(deliver_join_code_sms, req.mobile_number)
    return _onboard_ack()
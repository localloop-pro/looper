"""Seed LOOPER database with Bondi area businesses for testing.

Refuses to run against a production-shaped database (looper#111) unless
LOOPER_ALLOW_SEED=yes is set.
"""
import os
import sys
from collections.abc import Mapping

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROD_ENV_KEYS = ("COOLIFY_URL", "SOURCE_COMMIT", "LOOPER_COMMIT")


def refuse_reason(db_url: str, env: Mapping[str, str]) -> str | None:
    """Why seeding this target is refused, or None when it is safe. Pure."""
    if env.get("LOOPER_ALLOW_SEED") == "yes":
        return None
    if db_url.startswith("sqlite:///"):
        path = os.path.abspath(db_url[len("sqlite:///"):])
        if path.startswith("/app/"):
            return f"database file {path} is under /app/ (production image path)"
    if env.get("LOOPER_ENV") == "production":
        return "LOOPER_ENV=production"
    for key in PROD_ENV_KEYS:
        if env.get(key):
            return f"{key} is set (deployed environment)"
    for key in env:
        if key.startswith("COOLIFY_"):
            return f"{key} is set (Coolify environment)"
    return None


def seed(db) -> dict:
    """Insert the demo data (idempotent) and return row counts."""
    from models import Business, User, Review

    # Bondi businesses (real locations, generic names to avoid bias)
    businesses = [
        ("Bondi Wholefoods", "café", "32 Campbell Parade, Bondi Beach", -33.8908, 151.2748),
        ("The Health Emporium", "café", "263 Bondi Rd, Bondi", -33.8921, 151.2620),
        ("Gertrude & Alice", "café", "1/46 Hall St, Bondi Beach", -33.8893, 151.2735),
        ("Bondi Medical Centre", "doctor", "70 Spring St, Bondi Junction", -33.8925, 151.2490),
        ("Bondi Junction Medical", "doctor", "251 Oxford St, Bondi Junction", -33.8916, 151.2498),
        ("Bondi Vet", "vet", "74 Ebley St, Bondi Junction", -33.8930, 151.2495),
        ("Rose Bay Vet", "vet", "757 New South Head Rd, Rose Bay", -33.8720, 151.2650),
        ("Bondi Plumbing Co", "plumber", "12 Blair St, Bondi", -33.8915, 151.2650),
        ("Eastern Suburbs Dental", "dentist", "157 Bondi Rd, Bondi", -33.8930, 151.2630),
        ("Bondi Beach Dental", "dentist", "178 Campbell Parade, Bondi Beach", -33.8895, 151.2750),
        ("LocalLoop Pharmacy", "pharmacy", "180 Campbell Parade, Bondi Beach", -33.8895, 151.2755),
        ("Bondi Road Physio", "physiotherapist", "185 Bondi Rd, Bondi", -33.8935, 151.2635),
        ("Bondi Hair Studio", "hairdresser", "95 Bondi Rd, Bondi", -33.8940, 151.2640),
        ("Bondi Yoga Collective", "fitness", "72 Gould St, Bondi Beach", -33.8885, 151.2730),
        ("Icebergs Dining Room", "restaurant", "1 Notts Ave, Bondi Beach", -33.8960, 151.2765),
        ("Bondi Hardware", "restaurant", "39 Hall St, Bondi Beach", -33.8895, 151.2735),
        ("Speedo's Café", "café", "126 Ramsgate Ave, North Bondi", -33.8870, 151.2780),
        ("Bondi Markets", "retail", "Campbell Parade, Bondi Beach", -33.8910, 151.2750),
        ("Bondi Electrical", "electrician", "22A Curlewis St, Bondi", -33.8920, 151.2645),
        ("North Bondi Fish", "restaurant", "120 Ramsgate Ave, North Bondi", -33.8872, 151.2780),
    ]

    for name, category, address, lat, lng in businesses:
        existing = db.query(Business).filter(Business.name == name).first()
        if not existing:
            biz = Business(
                name=name,
                category=category,
                address=address,
                suburb="Bondi" if "Bondi" in address else "Rose Bay",
                lat=lat,
                lng=lng,
                source="manual",
            )
            db.add(biz)

    db.commit()

    # Add a seed user for testing
    user = db.query(User).filter(User.mobile_number == "0400000001").first()
    if not user:
        user = User(
            first_name="Demo",
            mobile_number="0400000001",
            join_code="123456",
            user_type="local",
            interest_category="testing",
        )
        db.add(user)
        db.commit()

    # Add sample reviews (from "local users")
    sample_reviews = [
        (1, 5, "Best açai bowl in Bondi! Fresh fruit, generous portions, and great coffee. Been coming here every Saturday for 2 years.", user.id),
        (1, 4, "Good healthy options but gets really busy on weekends. The smoothies are amazing though.", user.id),
        (3, 5, "My go-to spot for a chill afternoon. Great atmosphere and the staff remember your name. Love their chai latte.", user.id),
        (5, 4, "Dr. Chen is thorough and caring. Waited about 20 mins past appointment time but the care was worth it.", user.id),
        (6, 5, "They saved our puppy when she ate chocolate! Emergency after-hours service, incredibly compassionate team. Can't recommend enough.", user.id),
        (8, 3, "Fixed our blocked drain but was a bit pricey. Got the job done though, no issues since.", user.id),
        (14, 5, "Best yoga studio in Bondi — ocean views from the studio, incredible teachers. Community vibe is wonderful.", user.id),
        (15, 5, "Iconic Bondi dining experience. Pricey but worth it for the view and the seafood. Book ahead for sunset.", user.id),
        (16, 4, "Great cocktails and share plates. Outdoor courtyard is lovely in summer. Can get noisy inside.", user.id),
        (17, 5, "Hidden gem! Best coffee in North Bondi and the breakfast burrito is legendary. Dog-friendly too 🐕", user.id),
        (20, 5, "Fresh seafood right on the beach. The battered fish is crispy perfection. A proper Bondi institution.", user.id),
    ]

    for biz_id, rating, text, uid in sample_reviews:
        existing = db.query(Review).filter(Review.business_id == biz_id, Review.review_text == text).first()
        if not existing:
            review = Review(
                business_id=biz_id,
                user_id=uid,
                rating=rating,
                review_text=text,
                verified_visit=True,
            )
            db.add(review)

    db.commit()

    return {
        "businesses": db.query(Business).count(),
        "reviews": db.query(Review).count(),
        "users": db.query(User).count(),
    }


def main(argv=None) -> int:
    import models

    db_url = models.DATABASE_URL
    print(f"seed target: {db_url}")
    reason = refuse_reason(db_url, os.environ)
    if reason:
        print(f"refused: {reason}. Set LOOPER_ALLOW_SEED=yes only if you are sure.")
        return 2
    if os.environ.get("LOOPER_ALLOW_SEED") == "yes":
        print("WARNING: LOOPER_ALLOW_SEED=yes, production guard bypassed")
    models.init_db()
    db = models.SessionLocal()
    try:
        counts = seed(db)
    finally:
        db.close()
    print(f"✅ Seeded: {counts['businesses']} businesses, {counts['reviews']} reviews, {counts['users']} users")
    return 0


if __name__ == "__main__":
    sys.exit(main())

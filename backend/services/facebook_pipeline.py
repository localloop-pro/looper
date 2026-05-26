"""Facebook Group Data Pipeline for LOOPER

Collects raw review and recommendation data from the Bondi Local Loop
Facebook group (~150,000 members) and imports into LOOPER database.

Architecture:
1. Facebook Graph API → fetch group posts
2. NLP classifier → identify review/recommendation posts
3. Entity extractor → pull out business names, categories, sentiments
4. DB importer → create/update LOOPER Business + Review records

Requirements:
- Facebook App with groups_access_member_info permission
- Group admin access token (long-lived)
- group_id for Bondi Local Loop
"""

import re
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("looper.facebook")


# ── Business name patterns for Bondi area ──
BONDI_BUSINESS_PATTERNS = [
    # Format: (regex, category) — tighter patterns to avoid false matches
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:caf[ée]|coffee)\b", "café"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:medical\s*centre|clinic|doctor|GP)\b", "doctor"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:vet\b|veterinary)", "vet"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:dental|dentist)\b", "dentist"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:plumb(?:er|ing))\b", "plumber"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:restaurant|bistro|dining|eatery)\b", "restaurant"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:pharmacy|chemist)\b", "pharmacy"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:physio|physical\s+therapy)\b", "physiotherapist"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:hairdresser|barber|salon)\b", "hairdresser"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:yoga|gym|fitness|pilates)\b", "fitness"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:electrician|electrical)\b", "electrician"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:bakery|baker)\b", "bakery"),
    (r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:mechanic|auto)\b", "mechanic"),
]

# Words that should NOT appear as business names (adjectives, verbs, etc.)
NON_NAME_WORDS = {
    "good", "great", "best", "amazing", "fantastic", "wonderful", "excellent",
    "new", "old", "nice", "lovely", "friendly", "local", "nearby", "closest",
    "avoid", "try", "recommend", "recommended", "anyone", "someone", "looking",
    "need", "want", "find", "found", "use", "used", "using", "know", "knows",
    "terrible", "awful", "horrible", "worst", "bad", "poor", "disappointing",
}

# Stop-phrases that indicate a post is NOT a review
NOT_A_REVIEW = [
    "for sale", "selling", "wanted", "looking for room",
    "iso", "in search of", "lost cat", "lost dog", "found",
    "spam", "scam", "warning",
]


def classify_post(text: str) -> dict:
    """Classify a Facebook post: is it a review/recommendation? Extract entities."""
    text_lower = text.lower()

    # Check if it's clearly not a review
    for phrase in NOT_A_REVIEW:
        if phrase in text_lower:
            return {"is_review": False, "confidence": 0.0, "reason": f"matched stop-phrase: '{phrase}'", "businesses": [], "sentiment": "neutral", "estimated_rating": 0, "summary": text[:200].strip()}

    # Check for recommendation indicators
    recommendation_signals = [
        "recommend", "recommended", "best", "amazing", "fantastic",
        "great service", "love this", "go to", "favourite", "favorite",
        "⭐", "★", "5 stars", "5/5", "10/10", "can't recommend enough",
        "highly recommend", "must try", "hidden gem", "best in",
    ]

    score = sum(1 for sig in recommendation_signals if sig in text_lower)

    # Extract business mentions
    businesses = []
    for pattern, category in BONDI_BUSINESS_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            name = match.strip()
            # Filter out non-name words
            words = name.split()
            clean_words = [w for w in words if w.lower() not in NON_NAME_WORDS]
            if not clean_words:
                continue
            name = " ".join(clean_words)
            if len(name) > 3 and len(name) < 80:
                businesses.append({"name": name, "category": category})

    # Sentiment
    sentiment = "neutral"
    positive_words = ["great", "amazing", "fantastic", "excellent", "best", "love", "wonderful", "perfect", "outstanding", "brilliant"]
    negative_words = ["terrible", "awful", "worst", "horrible", "bad", "poor", "disappointing", "rude", "avoid", "never again"]

    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    if pos_count > neg_count + 1:
        sentiment = "positive"
    elif neg_count > pos_count + 1:
        sentiment = "negative"

    # Estimate rating from sentiment
    rating_map = {"positive": 5, "neutral": 3, "negative": 1}
    estimated_rating = rating_map[sentiment]

    # Extract rating if explicitly mentioned
    rating_match = re.search(r"(\d)[\s/]*(?:5|stars|out of 5)", text)
    if rating_match:
        estimated_rating = int(rating_match.group(1))

    return {
        "is_review": score >= 1,
        "confidence": min(score / 3, 1.0),
        "businesses": businesses,
        "sentiment": sentiment,
        "estimated_rating": estimated_rating,
        "summary": text[:200].strip(),
    }


def import_to_db(post_data: dict, db_session) -> list:
    """Import a classified Facebook post into LOOPER database. Returns list of review IDs."""
    from models import Business, Review, User

    if not post_data.get("is_review"):
        return []

    # Find or create FB source user
    fb_user = db_session.query(User).filter(
        User.mobile_number == f"fb_{post_data.get('author_id', 'unknown')}"
    ).first()
    if not fb_user:
        fb_user = User(
            first_name=post_data.get("author_name", "FB User")[:100],
            mobile_number=f"fb_{post_data.get('author_id', hashlib.md5(str(datetime.now()).encode()).hexdigest()[:12])}",
            user_type="local",
            interest_category="facebook_member",
        )
        db_session.add(fb_user)
        db_session.flush()

    review_ids = []
    for biz in post_data.get("businesses", []):
        # Find or create business
        business = db_session.query(Business).filter(
            Business.name.ilike(f"%{biz['name']}%"),
            Business.category == biz["category"],
        ).first()
        if not business:
            business = Business(
                name=biz["name"],
                category=biz["category"],
                suburb="Bondi",
                source="facebook",
            )
            db_session.add(business)
            db_session.flush()

        # Add review
        review = Review(
            business_id=business.id,
            user_id=fb_user.id,
            rating=post_data.get("estimated_rating", 3),
            review_text=post_data.get("summary", ""),
            verified_visit=False,
            source="facebook_import",
            facebook_post_id=post_data.get("post_id"),
        )
        db_session.add(review)
        db_session.flush()
        review_ids.append(review.id)

    return review_ids


def run_pipeline(graph_api_token: str = "", group_id: str = "", limit: int = 50):
    """
    Main pipeline: fetch FB posts → classify → import → report.

    Args:
        graph_api_token: Facebook Graph API access token
        group_id: Facebook group ID (Bondi Local Loop)
        limit: Max posts to process per run
    """
    import requests
    from models import SessionLocal, init_db

    init_db()
    db = SessionLocal()

    if not graph_api_token or not group_id:
        logger.warning("No FB credentials — running in demo mode with sample posts")
        sample_posts = [
            {
                "post_id": "demo_1",
                "author_id": "fb_user_001",
                "author_name": "Sarah M.",
                "message": "Can anyone recommend a good café near Bondi Beach? I've been going to Bondi Wholefoods for years — best açai bowl and the coffee is perfect. 5/5 ⭐",
                "created_time": "2026-05-20T08:30:00+00:00",
            },
            {
                "post_id": "demo_2",
                "author_id": "fb_user_002",
                "author_name": "James K.",
                "message": "Just had the most amazing dinner at Icebergs Dining Room. The seafood platter was incredible and the view at sunset is unbeatable. Highly recommend for special occasions!",
                "created_time": "2026-05-19T19:45:00+00:00",
            },
            {
                "post_id": "demo_3",
                "author_id": "fb_user_003",
                "author_name": "Emma L.",
                "message": "Bondi Vet saved our puppy last night! Emergency after-hours — the team was so compassionate and professional. Can't recommend them enough. 5 stars ⭐⭐⭐⭐⭐",
                "created_time": "2026-05-18T23:15:00+00:00",
            },
            {
                "post_id": "demo_4",
                "author_id": "fb_user_004",
                "author_name": "Tom R.",
                "message": "Anyone know a good plumber in Bondi? Our drain is blocked again. Used Bondi Plumbing Co last time but they were expensive and just average. Looking for alternatives.",
                "created_time": "2026-05-18T14:20:00+00:00",
            },
            {
                "post_id": "demo_5",
                "author_id": "fb_user_005",
                "author_name": "Lisa W.",
                "message": "Speedo's Café in North Bondi is my weekend ritual. Best coffee and the breakfast burrito is legendary. Dog-friendly too which is a bonus! 🐕☕",
                "created_time": "2026-05-17T09:00:00+00:00",
            },
        ]
        posts = sample_posts
    else:
        # Real Facebook Graph API call
        url = f"https://graph.facebook.com/v19.0/{group_id}/feed"
        params = {
            "access_token": graph_api_token,
            "limit": limit,
            "fields": "id,message,from,created_time",
        }
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            logger.error(f"FB API error: {resp.status_code} {resp.text[:200]}")
            db.close()
            return
        posts = []
        for item in resp.json().get("data", []):
            posts.append({
                "post_id": item.get("id"),
                "author_id": item.get("from", {}).get("id", "unknown"),
                "author_name": item.get("from", {}).get("name", "Unknown"),
                "message": item.get("message", ""),
                "created_time": item.get("created_time"),
            })

    # Process each post
    imported = 0
    skipped = 0
    for post in posts:
        if not post.get("message"):
            skipped += 1
            continue

        classification = classify_post(post["message"])
        post.update(classification)

        if classification["is_review"]:
            result = import_to_db(post, db)
            if result:
                imported += len(result)
                logger.info(f"✓ Imported: {classification['summary'][:80]}...")
        else:
            skipped += 1

    db.commit()
    db.close()

    logger.info(f"\n{'='*50}")
    logger.info(f"Pipeline complete: {imported} reviews imported, {skipped} posts skipped")
    logger.info(f"{'='*50}")
    return imported, skipped


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LOOPER Facebook data pipeline")
    parser.add_argument("--token", help="Facebook Graph API access token")
    parser.add_argument("--group-id", help="Facebook group ID", default="BondiLocalLoop")
    parser.add_argument("--limit", type=int, default=50, help="Max posts to fetch")
    parser.add_argument("--demo", action="store_true", help="Run with demo data")
    args = parser.parse_args()

    if args.demo or (not args.token):
        run_pipeline(limit=args.limit)
    else:
        run_pipeline(graph_api_token=args.token, group_id=args.group_id, limit=args.limit)
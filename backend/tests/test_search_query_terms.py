"""looper#29 / BLIND-SPOTS §3.16: synonym + compound-word table for search.

"hairdresser" (one word) must find a hair business filed under an unrelated
category (live Aesthete Hair is "professional"), without a blanket substring
rule that would let "carpet cleaner" match "Car Wash".
"""
import pytest

from models import Business, Review, User
from services import query_terms
from tests.conftest import sample_deal_payload, signed_post


def _biz(db, name, category, description=None, **kw):
    biz = Business(name=name, category=category, description=description,
                   suburb="Bondi", lat=-33.8915, lng=151.2650,
                   source=kw.pop("source", "manual"), **kw)
    db.add(biz)
    db.flush()
    return biz


def _reviews(db, biz, n):
    user = db.query(User).first()
    if user is None:
        user = User(first_name="Tester", mobile_number="0400000099")
        db.add(user)
        db.flush()
    for i in range(n):
        db.add(Review(business_id=biz.id, user_id=user.id, rating=4,
                      review_text=f"Visit {i + 1} was fine."))


@pytest.fixture()
def seeded(db):
    _biz(db, "Aesthete Hair", "professional", "Colour, cuts and styling")
    _biz(db, "Bondi Car Wash", "car wash", "Hand car wash and detailing")
    _biz(db, "Bondi Chair Hire", "events", "Party chairs and tables")
    _biz(db, "Speedo's Café", "café", "Breakfast by the beach")
    db.commit()
    return db


def _names(client, q):
    resp = client.get("/api/search", params={"q": q})
    assert resp.status_code == 200
    return [r["name"] for r in resp.json()["results"]]


@pytest.mark.parametrize("q", ["hairdresser", "Hairdresser", "hairdressers",
                               "hair dresser", "salon", "barber",
                               "find me a hairdresser", "hairdresser in Bondi"])
def test_hair_words_find_the_hair_business(client, seeded, q):
    assert "Aesthete Hair" in _names(client, q)


def test_carpet_cleaner_never_matches_car_wash(client, seeded):
    assert "Bondi Car Wash" not in _names(client, "carpet cleaner")


def test_added_alternatives_must_start_a_word(client, seeded):
    # "hairdresser" adds "hair"; "Chair Hire" contains "hair" mid-word.
    assert "Bondi Chair Hire" not in _names(client, "hairdresser")


# PR #34 QA: what web/jarvis/voice-command-router.js sends for a spoken hair
# word — now, and the padded terms the first draft sent (cached widgets) —
# must return exactly what typed "hairdresser" returns. Never Chair Hire.
@pytest.mark.parametrize("q", [
    "hairdresser", "hair dresser hairdresser", "hairdressers hairdresser",
    "salon", "hair salon salon", "barber", "barbers barber",
    "hair dresser", "hairdresser salon hair", "barber hair",
])
def test_spoken_and_typed_hair_words_agree(client, seeded, q):
    names = _names(client, q)
    assert "Aesthete Hair" in names
    assert "Bondi Chair Hire" not in names
    assert sorted(names) == sorted(_names(client, "hairdresser"))


def test_padded_word_follows_the_word_start_rule():
    groups = query_terms.expand(["barber", "hair"])
    [hair] = [t for t in groups[1] if t.text == "hair"]
    assert hair.original and not hair.anywhere


def test_bare_hair_still_matches_as_substring(client, seeded):
    # Typed "hair" behaved like this on main; this PR keeps it.
    assert query_terms.expand(["hair"])[0][0].anywhere
    assert "Aesthete Hair" in _names(client, "hair")


def test_cafe_and_coffee_agree(client, seeded):
    for q in ("cafe", "café", "coffee", "cafes"):
        assert "Speedo's Café" in _names(client, q), q


def test_expansion_keeps_the_original_word():
    groups = query_terms.expand(["hairdresser"])
    assert len(groups) == 1
    texts = [t.text for t in groups[0]]
    assert texts[0] == "hairdresser" and groups[0][0].original
    assert {"hair", "salon"} <= set(texts)


def test_compound_is_one_group_with_both_originals():
    [group] = query_terms.expand(["hair", "dresser"])
    originals = [t.text for t in group if t.original]
    assert originals == ["hair", "dresser"]
    assert "salon" in [t.text for t in group]


def test_unknown_words_pass_through_unchanged():
    [group] = query_terms.expand(["florist"])
    assert [(t.text, t.original) for t in group] == [("florist", True)]


def test_table_is_folded_lowercase():
    from models import fold_accents
    for key, alts in query_terms.EXPANSIONS.items():
        assert key == fold_accents(key)
        assert all(a == fold_accents(a) for a in alts)


# ---- anti-bias: card_url / discount / source / rank_boost never reorder ----

def test_hair_order_ignores_card_discount_source_and_boost(client, db):
    """Three hair businesses: order = relevance, then reviews. The
    least-reviewed one arrives over the signed bridge with a card URL and a
    plain deal, then again with a 90% discount and rank_boost forced true —
    the order must not move."""
    a = _biz(db, "Alpha Hair", "hairdresser")
    b = _biz(db, "Beta Hair", "hairdresser")
    _reviews(db, a, 3)
    _reviews(db, b, 2)
    db.commit()

    def ingest(event_id, updated_at, **kw):
        payload = sample_deal_payload(
            eventId=event_id, business_name="Gamma Hair", category="hairdresser",
            sub_type="salon", hybrid_card_id="card-gamma", deal_id="deal-gamma",
            public_card_url="https://gamma.hybridcard.ai", lat=-33.8915,
            lng=151.2650, updated_at=updated_at, **kw)
        assert signed_post(client, "/api/ingest/hybridcard-deal", payload).status_code == 200

    ingest("evt-g1", "2026-07-11T00:00:00.000Z", discount_size=0, rank_boost=False)
    before = _names(client, "hairdresser")
    assert before == ["Alpha Hair", "Beta Hair", "Gamma Hair"]

    ingest("evt-g2", "2026-07-12T00:00:00.000Z", discount_size=90, rank_boost=True)
    gamma = db.query(Business).filter(Business.name == "Gamma Hair").one()
    db.refresh(gamma)
    assert gamma.source == "hybrid_card"  # source differs from Alpha/Beta ("manual")

    resp = client.get("/api/search", params={"q": "hairdresser"}).json()
    assert [r["name"] for r in resp["results"]] == before
    # the card link is returned as stored, never used for ordering
    card = next(r for r in resp["results"] if r["name"] == "Gamma Hair")
    assert card["card_url"] == "https://gamma.hybridcard.ai"
    # and the same holds for every hair spelling
    for q in ("Hairdresser", "hairdressers", "hair dresser", "salon"):
        assert _names(client, q) == before, q


def test_expanded_word_scores_once(client, db):
    """A business that hits several alternatives of ONE word ("Hair Salon"
    for "hairdresser") must not outrank a better-reviewed hairdresser."""
    _biz(db, "Hair Salon Bondi", "beauty")
    studio = _biz(db, "Hair by Kim", "beauty")
    _reviews(db, studio, 2)
    db.commit()
    assert _names(client, "hairdresser") == ["Hair by Kim", "Hair Salon Bondi"]

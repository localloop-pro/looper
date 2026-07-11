"""Anti-bias invariant tests (BRIDGE-CONTRACT-v1 §7, AGENTS.md rule 1).

Ranking = relevance + review count + proximity ONLY. A huge discount and a
forced rank_boost must never outrank community reviews.
"""
import inspect

from models import Business, Review, User
from tests.conftest import sample_deal_payload, signed_post


def test_reviews_outrank_discounts(client, db):
    # Business A: 3 reviews, no deal — created directly.
    biz_a = Business(name="Reviewed Cafe A", category="café", suburb="Bondi",
                     lat=-33.8908, lng=151.2748, source="manual")
    db.add(biz_a)
    user = User(first_name="Tester", mobile_number="0400000099")
    db.add(user)
    db.flush()
    for i in range(3):
        db.add(Review(business_id=biz_a.id, user_id=user.id, rating=5,
                      review_text=f"Great coffee, visit number {i + 1} was lovely!"))
    db.commit()

    # Business B: zero reviews, ingested deal with a 90% discount and
    # rank_boost forced true in the payload (receiver must ignore it).
    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(business_name="Discount Cafe B",
                                           discount_size=90, rank_boost=True))
    assert resp.status_code == 200

    results = client.get("/api/search", params={"q": "café"}).json()["results"]
    names = [r["name"] for r in results]
    assert names.index("Reviewed Cafe A") < names.index("Discount Cafe B")


def test_ranking_code_never_references_bridge_fields():
    """Static guard: executable ranking code cannot mention bridge-only
    fields. Comment lines are stripped (the invariant comment may name them)."""
    import routes.search
    src = inspect.getsource(routes.search)
    code_lines = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    code = "\n".join(code_lines)
    assert "discount" not in code
    assert "rank_boost" not in code
    # the sort key itself is load-bearing — fail loudly if someone edits it
    assert 'results.sort(key=lambda r: (-r["relevance"], -r["review_count"], r["distance_km"] or 999))' in code


def test_deactivated_business_hidden_from_search(client, db):
    biz = Business(name="Ghost Cafe", category="café", suburb="Bondi",
                   lat=-33.89, lng=151.27, source="manual", is_active=False)
    db.add(biz)
    db.commit()
    results = client.get("/api/search", params={"q": "Ghost"}).json()["results"]
    assert results == []

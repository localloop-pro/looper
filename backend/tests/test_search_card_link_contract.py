"""looper#38 — /api/search card link contract for the map's Jarvis dock.

Looper sends ``card_url`` as the only card link. ``slug`` is never in a
search result, even when the card event carried one, because Business has
no slug column and adding one would change the schema of live data (a hot
zone that needs the owner's OK). The map (localloop.pro-main) must stop
reading ``r.slug`` and use ``card_url`` as sent.

The card URL is returned exactly as the sender gave it, for any host
(tunnel hosts too). It is never rebuilt from a slug and never moves the order.
"""
from models import Business, Review, User
from tests.conftest import sample_deal_payload, signed_post
from tests.test_ingest_card import PATH as CARD_PATH, sample_card_payload

TUNNEL_URL = "https://quiet-river-1234.trycloudflare.com/c/bondi-cafe"


def test_search_results_never_carry_slug_even_when_card_sent_one(client, db):
    resp = signed_post(client, CARD_PATH, sample_card_payload(slug="bondi-cafe"))
    assert resp.status_code == 200

    results = client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"]
    assert results, "the ingested card should be searchable"
    for r in results:
        assert "slug" not in r
        assert "card_url" in r


def test_tunnel_host_card_url_returned_verbatim(client, db):
    resp = signed_post(client, CARD_PATH,
                       sample_card_payload(slug="bondi-cafe", public_card_url=TUNNEL_URL))
    assert resp.status_code == 200

    results = client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"]
    assert results[0]["card_url"] == TUNNEL_URL


def test_tunnel_deal_card_url_returned_verbatim(client, db):
    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(public_card_url=TUNNEL_URL))
    assert resp.status_code == 200

    results = client.get("/api/search", params={"q": "Bondi Cafe"}).json()["results"]
    assert results[0]["card_url"] == TUNNEL_URL


def test_card_url_never_changes_order(client, db):
    """Anti-bias: a reviewed business without a card still outranks a carded,
    discounted, rank_boosted one with zero reviews."""
    biz = Business(name="Bondi Reviewed Cafe", category="café", suburb="Bondi",
                   lat=-33.8908, lng=151.2748, source="manual")
    db.add(biz)
    user = User(first_name="Tester", mobile_number="0400000038")
    db.add(user)
    db.flush()
    for i in range(2):
        db.add(Review(business_id=biz.id, user_id=user.id, rating=4,
                      review_text=f"Good flat white, visit {i + 1}."))
    db.commit()

    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(business_name="Bondi Carded Cafe",
                                           public_card_url=TUNNEL_URL,
                                           discount_size=90, rank_boost=True))
    assert resp.status_code == 200

    results = client.get("/api/search", params={"q": "Bondi"}).json()["results"]
    names = [r["name"] for r in results]
    assert len(names) >= 2
    assert names.index("Bondi Reviewed Cafe") < names.index("Bondi Carded Cafe")
    carded = next(r for r in results if r["name"] == "Bondi Carded Cafe")
    assert carded["card_url"] == TUNNEL_URL

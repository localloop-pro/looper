"""F3.x voice-support backend tests: accent-folded search (the café/cafe
gotcha), HybridCard card_url exposure, and the read-only ingest status
cockpit endpoint."""
from datetime import datetime, timezone

from models import Business, BridgeEvent, Deal


def _biz(db, **kw):
    defaults = dict(
        name="Gertrude & Alice",
        category="café",
        suburb="Bondi Beach",
        lat=-33.8893,
        lng=151.2735,
        description="Bookshop café",
        is_active=True,
        source="manual",
    )
    defaults.update(kw)
    b = Business(**defaults)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


class TestAccentFoldedSearch:
    def test_ascii_query_finds_accented_category(self, client, db):
        """Voice transcripts type 'cafe'; the seed data says 'café'."""
        _biz(db)
        resp = client.get("/api/search", params={"q": "cafe"})
        assert resp.status_code == 200
        names = [r["name"] for r in resp.json()["results"]]
        assert "Gertrude & Alice" in names

    def test_accented_query_still_works(self, client, db):
        _biz(db)
        resp = client.get("/api/search", params={"q": "café"})
        assert resp.status_code == 200
        assert resp.json()["results"], "accented query must keep working"

    def test_accent_fold_in_name(self, client, db):
        _biz(db, name="Café Salina", category="restaurant")
        resp = client.get("/api/search", params={"q": "cafe salina"})
        assert resp.status_code == 200
        assert resp.json()["results"][0]["name"] == "Café Salina"


class TestHybridCardLinkExposure:
    def test_card_url_from_active_deal(self, client, db):
        b = _biz(db, hybrid_card_id="hc_123")
        db.add(Deal(
            deal_id="deal_1",
            business_id=b.id,
            title="10% off",
            active=True,
            public_card_url="https://gertrude.hybridcard.ai",
        ))
        db.commit()
        resp = client.get("/api/search", params={"q": "cafe"})
        result = resp.json()["results"][0]
        assert result["card_url"] == "https://gertrude.hybridcard.ai"

    def test_card_url_from_card_website(self, client, db):
        _biz(db, hybrid_card_id="hc_456",
             website="https://alice.hybridcard.ai")
        resp = client.get("/api/search", params={"q": "cafe"})
        assert resp.json()["results"][0]["card_url"] == "https://alice.hybridcard.ai"

    def test_no_card_no_url(self, client, db):
        _biz(db, website="https://example.com")
        result = client.get("/api/search", params={"q": "cafe"}).json()["results"][0]
        assert result["card_url"] is None
        assert result["website"] == "https://example.com"

    def test_card_url_never_affects_ranking(self, client, db):
        """Anti-bias: a card-holding business must NOT outrank a better
        reviewed one. Both zero reviews here → original relevance order,
        card presence irrelevant."""
        _biz(db, name="Plain Cafe No Card", category="café")
        _biz(db, name="Card Cafe", category="café", hybrid_card_id="hc_x",
             website="https://card.hybridcard.ai")
        names = [r["name"] for r in
                 client.get("/api/search", params={"q": "cafe"}).json()["results"]]
        assert set(names) == {"Plain Cafe No Card", "Card Cafe"}
        # equal relevance + equal reviews → insertion order preserved; the
        # carded business gains nothing from its card
        assert names[0] == "Plain Cafe No Card"


class TestIngestStatus:
    def test_status_counts_and_recent(self, client, db):
        db.add(BridgeEvent(event_id="evt_1", event_type="deal.upserted",
                           payload="{}", status="processed",
                           received_at=datetime.now(timezone.utc)))
        db.add(BridgeEvent(event_id="evt_2", event_type="deal.removed",
                           payload="{}", status="processed",
                           received_at=datetime.now(timezone.utc)))
        db.commit()
        resp = client.get("/api/ingest/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["counts"]["total_events"] == 2
        assert body["counts"]["by_type"]["deal.upserted"] == 1
        ids = [e["event_id"] for e in body["recent_events"]]
        assert "evt_1" in ids and "evt_2" in ids
        # public-safe: no payload bodies in the cockpit
        assert all("payload" not in e for e in body["recent_events"])

    def test_status_empty_db(self, client, db):
        resp = client.get("/api/ingest/status")
        assert resp.status_code == 200
        assert resp.json()["counts"]["total_events"] == 0

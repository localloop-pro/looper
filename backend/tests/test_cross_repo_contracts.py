"""Cross-repo contract tests (looper#31) — one test per inbound call listed in
docs/CROSS-REPO-CONTRACTS.md.

Each test sends the CALLER's real request shape, copied from its code at the
pinned commit below, and asserts only what that caller actually reads. If a
test here fails, a live caller in another repo breaks — fix Looper, or file a
"Contract mismatch: …" issue; never edit the sender's shape to make it pass
(BRIDGE-CONTRACT-v1 is frozen, receivers adapt).

Pinned sources:
  HC  = localloop-pro/hybridcard-v2      @ 55b7ced413f0e01a53517c17809387dafd81851f
  MAP = localloop-pro/localloop.pro-main @ 761d3a124dd4965c3454dc28e6050ebfbf7f2b36
"""
import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from models import BridgeEvent, Business, Deal, Review, User
from services import bridge_hmac

HC = "https://github.com/localloop-pro/hybridcard-v2/blob/55b7ced413f0e01a53517c17809387dafd81851f"
MAP = "https://github.com/localloop-pro/localloop.pro-main/blob/761d3a124dd4965c3454dc28e6050ebfbf7f2b36"


# ── sender helpers: mirror HybridCard's drain exactly ─────────────────────

def js_stringify(payload: dict) -> bytes:
    """JSON.stringify(ev.payload) — compact separators, raw UTF-8 ("café" is
    NOT \\u-escaped), keys with `undefined` values dropped.
    Source: {HC}/src/lib/bridge/outbox.ts#L487"""
    clean = {k: v for k, v in payload.items() if v is not None}
    return json.dumps(clean, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hc_post(client, path: str, payload: dict):
    """defaultPost + signBody(body, secret) with the default keyId 'hc-1'.
    Sources: {HC}/src/lib/bridge/outbox.ts#L242-L250, #L488;
             {HC}/src/lib/bridge/hmac.ts#L15-L23"""
    raw = js_stringify(payload)
    headers = bridge_hmac.sign(raw, "test-secret", "hc-1", int(time.time() * 1000))
    return client.post(path, content=raw, headers={"Content-Type": "application/json", **headers})


def hc_deal_payload(**overrides) -> dict:
    """buildLooperPayload() output, field for field, in emit order.
    Source: {HC}/src/lib/bridge/payload.ts#L205-L228"""
    payload = {
        "source": "hybridcard",
        "eventId": "0b8f6c1e-6a43-4c55-9d1e-1f2a3b4c5d6e",  # randomUUID()
        "hybrid_card_id": "66f1a2b3c4d5e6f708192a3b",   # String(card._id)
        "deal_id": "66f1a2b3c4d5e6f708192a3c",          # String(deal._id)
        "business_name": "Bondi Contract Café",
        "category": "café",                              # archetype food → café
        "pin_type": "offering",
        "sub_type": "cafe",
        "title": "2-for-1 flat whites",
        "short_description": "Weekday mornings",
        "discount_size": 50,
        "lat": -33.8908,
        "lng": 151.2748,
        "hours": "Mon-Fri 7-3",
        # claimUrlForSlug: non-prod emits path form — must come back as sent.
        "public_card_url": "http://localhost:3000/c/bondi-contract-cafe",
        "active": True,
        "updated_at": "2026-10-01T00:00:00.000Z",
        "rank_boost": False,
    }
    payload.update(overrides)
    return payload


def hc_card_payload(**overrides) -> dict:
    """buildLooperCardPayload() output, field for field, in emit order.
    Source: {HC}/src/lib/bridge/payload.ts#L256-L279 (capabilities from
    {HC}/src/lib/cards/modulesEnabled.ts#L70-L87)"""
    payload = {
        "event_kind": "card",
        "eventId": "1c9e7d2f-7b54-4d66-8e2f-2a3b4c5d6e7f",
        "hybrid_card_id": "66f1a2b3c4d5e6f708192a3b",
        "slug": "bondi-contract-cafe",
        "business_name": "Bondi Contract Café",
        "category": "café",
        "sub_type": "cafe",
        "lat": -33.8908,
        "lng": 151.2748,
        "hours": "Mon-Fri 7-3",  # card.fields.hours is a string on the sender
        "public_card_url": "https://bondi-contract-cafe.hybridcard.ai",
        "archetype": "food",
        "status": "active",
        "active": True,
        "updated_at": "2026-10-01T00:00:00.000Z",
        "rank_boost": False,
        "capabilities": {
            "jobs": False, "offers": True, "deals": True, "shopping": False,
            "stays": False, "food": True, "bookings": False, "fetch": False,
            "news": True, "events": False,
        },
    }
    payload.update(overrides)
    return payload


# ── C1/C2: HybridCard outbox → /api/ingest/* ──────────────────────────────
# The sender reads ONLY res.ok / res.status ({HC}/src/lib/bridge/outbox.ts#L486-L511):
# 2xx → sent; anything else → retry, dead after MAX_ATTEMPTS=6.

def test_c1_hybridcard_deal_upsert_real_shape_is_2xx(client, db):
    r = hc_post(client, "/api/ingest/hybridcard-deal", hc_deal_payload())
    assert 200 <= r.status_code < 300, r.text
    deal = db.query(Deal).filter_by(deal_id="66f1a2b3c4d5e6f708192a3c").one()
    assert deal.active is True
    # Card URL stored exactly as sent (never rebuilt from slug, never host-gated).
    assert deal.public_card_url == "http://localhost:3000/c/bondi-contract-cafe"


def test_c1_hybridcard_deal_replay_is_2xx_and_idempotent(client, db):
    payload = hc_deal_payload()
    assert hc_post(client, "/api/ingest/hybridcard-deal", payload).status_code == 200
    again = hc_post(client, "/api/ingest/hybridcard-deal", payload)  # re-signed retry
    assert again.status_code == 200
    assert again.json().get("duplicate") is True
    assert db.query(BridgeEvent).count() == 1


def test_c1_hybridcard_deal_without_optional_hours_is_2xx(client, db):
    # card.fields.hours undefined → JSON.stringify drops the key entirely.
    r = hc_post(client, "/api/ingest/hybridcard-deal", hc_deal_payload(hours=None))
    assert r.status_code == 200, r.text


def test_c1_hybridcard_deal_removed_deactivates_not_deletes(client, db):
    hc_post(client, "/api/ingest/hybridcard-deal", hc_deal_payload())
    removed = hc_deal_payload(eventId="0b8f6c1e-0000-4c55-9d1e-1f2a3b4c5d6e", active=False,
                              updated_at="2026-10-02T00:00:00.000Z")
    assert hc_post(client, "/api/ingest/hybridcard-deal", removed).status_code == 200
    deal = db.query(Deal).filter_by(deal_id="66f1a2b3c4d5e6f708192a3c").one()
    assert deal.active is False


def test_c2_hybridcard_card_upsert_real_shape_is_2xx(client, db):
    r = hc_post(client, "/api/ingest/hybridcard-card", hc_card_payload())
    assert 200 <= r.status_code < 300, r.text
    biz = db.query(Business).filter_by(hybrid_card_id="66f1a2b3c4d5e6f708192a3b").one()
    assert biz.is_active is True
    assert biz.website == "https://bondi-contract-cafe.hybridcard.ai"


def test_c2_hybridcard_card_without_coords_is_2xx(client, db):
    # Card with no location: `const [lng, lat] = coords ?? [undefined, undefined]`
    # → both keys dropped by JSON.stringify; sub_type/hours may be undefined too.
    r = hc_post(client, "/api/ingest/hybridcard-card",
                hc_card_payload(lat=None, lng=None, sub_type=None, hours=None))
    assert r.status_code == 200, r.text


def test_c2_hybridcard_card_removed_deactivates_not_deletes(client, db):
    hc_post(client, "/api/ingest/hybridcard-card", hc_card_payload())
    removed = hc_card_payload(eventId="1c9e7d2f-0000-4d66-8e2f-2a3b4c5d6e7f", active=False,
                              status="draft", updated_at="2026-10-02T00:00:00.000Z")
    assert hc_post(client, "/api/ingest/hybridcard-card", removed).status_code == 200
    biz = db.query(Business).filter_by(hybrid_card_id="66f1a2b3c4d5e6f708192a3b").one()
    assert biz.is_active is False


def test_c2_card_payload_at_deal_url_is_rejected_today(client, db):
    """looper#36: with LOOPER_CARD_INGEST_URL unset the sender falls back to
    LOOPER_INGEST_URL ({HC}/src/lib/bridge/outbox.ts#L268-L270), i.e. the
    DEAL receiver. Pins today's 422 + nothing written so the fix chosen on
    #36 changes this test on purpose."""
    r = hc_post(client, "/api/ingest/hybridcard-deal", hc_card_payload())
    assert r.status_code == 422
    assert db.query(BridgeEvent).count() == 0
    assert db.query(Business).count() == 0


# ── shared read fixture ───────────────────────────────────────────────────

@pytest.fixture()
def seeded(client, db):
    """Two cafés near Bondi: one plain, one bridged from HybridCard (so
    card_url is populated). Reviews make avg_rating/top_review non-null."""
    user = User(first_name="Test", mobile_number="0400000000", join_code="ABC123")
    plain = Business(name="Plain Bean", category="café", suburb="Bondi Beach",
                     lat=-33.8910, lng=151.2745, website="https://plainbean.example")
    db.add_all([user, plain])
    db.commit()
    now = datetime.now(timezone.utc)
    db.add_all([
        Review(business_id=plain.id, user_id=user.id, rating=4,
               review_text="Great coffee and quick service.", created_at=now - timedelta(days=1)),
        Review(business_id=plain.id, user_id=user.id, rating=5,
               review_text="Friendly staff, would come back.", created_at=now),
    ])
    db.commit()
    assert hc_post(client, "/api/ingest/hybridcard-deal", hc_deal_payload()).status_code == 200
    return {"plain_id": plain.id}


# Fields each caller reads off results[] (see the doc's rows for file:line).
JARVIS_RESULT_FIELDS = {"name", "category", "avg_rating", "review_count", "distance_km",
                        "website", "card_url", "lat", "lng", "top_review"}
LEGACY_MAP_RESULT_FIELDS = {"name", "category", "distance_km", "avg_rating",
                            "review_count", "top_review"}
LOOPER_BOT_TABLE_FIELDS = {"name", "category", "avg_rating", "review_count",
                           "distance_km", "card_url", "website"}


def _assert_result_types(row: dict):
    assert isinstance(row["name"], str)
    assert isinstance(row["category"], str)
    assert isinstance(row["review_count"], int)
    for k in ("avg_rating", "distance_km", "lat", "lng"):
        assert row[k] is None or isinstance(row[k], (int, float)), k
    for k in ("top_review", "website", "card_url"):
        assert row[k] is None or isinstance(row[k], str), k


# ── C3: map Jarvis dock → GET /api/search ────────────────────────────────

def test_c3_jarvis_category_search(client, seeded):
    """runSearch: {MAP}/assets/js/jarvis/looper-jarvis.js#L1046-L1057"""
    r = client.get("/api/search", params={
        "q": "cafe", "lat": -33.8908, "lng": 151.2743, "radius_km": 2, "limit": 5,
        "intent": "search", "session": "lj-abc123",
    }, headers={"Origin": "https://localloop.ai"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://localloop.ai"
    data = r.json()
    assert isinstance(data["message"], str)
    assert isinstance(data["results"], list) and len(data["results"]) >= 2  # several options
    for row in data["results"]:
        assert JARVIS_RESULT_FIELDS <= row.keys()
        _assert_result_types(row)
    bridged = next(x for x in data["results"] if x["name"] == "Bondi Contract Café")
    assert bridged["card_url"] == "http://localhost:3000/c/bondi-contract-cafe"  # as sent


def test_c3_jarvis_business_lookup(client, seeded):
    """runBusiness: {MAP}/assets/js/jarvis/looper-jarvis.js#L1075-L1103"""
    r = client.get("/api/search", params={
        "q": "Plain Bean", "lat": -33.8908, "lng": 151.2743, "radius_km": 50, "limit": 3,
        "intent": "business", "session": "lj-abc123",
    })
    assert r.status_code == 200
    top = r.json()["results"][0]
    assert top["name"] == "Plain Bean"
    assert top["avg_rating"] == 4.5 and top["review_count"] == 2
    assert top["top_review"].startswith('"')  # spoken as-is: "One local said: …"
    assert top["lat"] is not None and top["lng"] is not None  # Bus.flyTo


def test_c3_jarvis_deeplink_name_lookup(client, seeded):
    """applyDeepLinks name lookup: {MAP}/assets/js/jarvis/looper-jarvis.js#L1301-L1302"""
    r = client.get("/api/search", params={"q": "Plain Bean", "limit": 1})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1


# ── C4: legacy map search (index.html inline + assets/js/main-map.js) ─────

def test_c4_legacy_map_search(client, seeded):
    """{MAP}/index.html#L15406-L15445 and {MAP}/assets/js/main-map.js#L3377-L3410
    send {q, limit:'5'} + optional lat/lng; read message + results[]."""
    r = client.get("/api/search", params={"q": "café", "limit": "5",
                                          "lat": -33.8908, "lng": 151.2743},
                   headers={"Origin": "https://www.localloop.ai"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://www.localloop.ai"
    data = r.json()
    assert isinstance(data["message"], str)
    for row in data["results"]:
        assert LEGACY_MAP_RESULT_FIELDS <= row.keys()


def test_c4_message_echoes_query_verbatim(client, db):
    """Pins the fact behind looper#37: `message` echoes the raw `q`, so a
    caller that drops it into innerHTML unescaped (index.html#L15422,
    main-map.js#L3393) renders caller-supplied markup. JSON is correct here —
    escaping belongs to the renderer. If Looper ever stops echoing, update
    the issue rather than this assert silently."""
    r = client.get("/api/search", params={"q": "<b>zzz</b>", "limit": "5"})
    assert "<b>zzz</b>" in r.json()["message"]


def test_c3_search_results_carry_no_slug(client, seeded):
    """Pins the fact behind looper#38: Jarvis passes r.slug as the fallback to
    canonicalClaimUrl ({MAP}/assets/js/jarvis/looper-jarvis.js#L801) but
    /api/search never returns one. card_url is the only card link."""
    for row in client.get("/api/search", params={"q": "cafe"}).json()["results"]:
        assert "slug" not in row


def test_c5_map_health_check_probe(client, seeded):
    """{MAP}/scripts/check-looper-health.cjs#L7-L25: sends an Origin header and
    fails on non-2xx, a CORS mismatch, or a missing results[] array."""
    r = client.get("/api/search", params={
        "q": "accommodation hotel", "lat": "-33.8915", "lng": "151.2743",
        "radius_km": "1.5", "limit": "5", "intent": "search",
    }, headers={"Origin": "https://localloop.ai"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://localloop.ai"
    assert isinstance(r.json()["results"], list)


# ── C6/C7: map + HybridCard → GET /api/identity/domains/{domain} ──────────

IDENTITY_FIELDS = {"domain", "network", "assetId", "inscriptionNumber", "transactionId",
                   "ownerAddress", "status", "verificationState", "verifiedAt",
                   "expiresAt", "explorerUrl"}  # = KaspaIdentityRecord in {HC}/src/lib/kaspaIdentity/types.ts#L3-L15


@pytest.fixture()
def fresh_identity(tmp_path, monkeypatch):
    from routes import identity as identity_route
    from services.kaspa_identity import EXPECTED_IDENTITIES, KaspaIdentityVerifier

    def handler(request):
        domain = request.url.params["asset"]
        e = EXPECTED_IDENTITIES[domain]
        return httpx.Response(200, json={"success": True, "data": {"assets": [{
            "id": str(e.inscription_number), "assetId": e.asset_id, "asset": domain,
            "owner": e.owner_address, "status": "default", "transactionId": e.transaction_id,
            "isDomain": True, "isVerifiedDomain": True,
        }]}})

    service = KaspaIdentityVerifier(cache_path=tmp_path / "id.json",
                                    transport=httpx.MockTransport(handler))
    monkeypatch.setattr(identity_route, "verifier", service)
    return service


@pytest.mark.parametrize("domain", ["localloop.kas", "qikflo.kas"])  # KASPA_ORGANIZATION_DOMAINS
def test_c6_hybridcard_identity_proxy(client, fresh_identity, domain):
    """{HC}/src/app/api/identity/domains/[domain]/route.ts#L16-L24 forwards
    with Accept: application/json and passes the JSON straight to
    KaspaIdentityBadge, which renders only verificationState === 'fresh'
    ({HC}/src/components/KaspaIdentityBadge.tsx#L33-L47)."""
    r = client.get(f"/api/identity/domains/{domain}", headers={"Accept": "application/json"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == IDENTITY_FIELDS
    assert body["verificationState"] == "fresh"
    assert body["network"] == "mainnet"
    assert isinstance(body["inscriptionNumber"], int)
    for k in ("assetId", "transactionId", "ownerAddress", "explorerUrl", "domain", "status"):
        assert isinstance(body[k], str) and body[k], k


def test_c6_unknown_domain_is_non_2xx(client, fresh_identity):
    # The proxy pre-filters to the two org domains; anything else from Looper
    # must be non-2xx so the proxy falls back to its 'unavailable' record.
    assert client.get("/api/identity/domains/attacker.kas").status_code == 404


def test_c7_map_kaspa_identity_browser_call(client, fresh_identity):
    """{MAP}/assets/js/kaspa-identity.js#L44-L46: browser fetch from the map
    origin, credentials 'omit'; reads verificationState, domain,
    ownerAddress, assetId, verifiedAt, explorerUrl (#L12-L36)."""
    r = client.get("/api/identity/domains/localloop.kas",
                   headers={"Accept": "application/json", "Origin": "https://localloop.ai"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://localloop.ai"
    body = r.json()
    assert body["verificationState"] in {"fresh", "stale", "mismatch", "unavailable"}
    assert body["explorerUrl"].startswith("https://")


# ── C8–C10: in-repo looper-bot (pinned so the doc's table is complete) ────

def test_c8_looper_bot_search(client, seeded):
    """looper-bot/electron/main.cjs#L1079-L1087 → businessesTable #L1069-L1077"""
    r = client.get("/api/search", params={"q": "cafe", "limit": 5})
    data = r.json()
    assert isinstance(data["message"], str)
    for row in data["results"]:
        assert LOOPER_BOT_TABLE_FIELDS <= row.keys()


def test_c9_looper_bot_discover(client, seeded):
    """looper-bot/electron/main.cjs#L1104-L1113 reads engine, message, results[]."""
    r = client.get("/api/discover", params={"suburb": "Bondi", "category": "café", "limit": 10,
                                            "intent": "discover", "session": "looper-desktop"})
    assert r.status_code == 200
    data = r.json()
    assert data["engine"] in {"fallback", "graph"}
    assert isinstance(data["message"], str)
    assert len(data["results"]) >= 2
    for row in data["results"]:
        assert LOOPER_BOT_TABLE_FIELDS <= row.keys()


def test_c10_looper_bot_businesses(client, seeded):
    """looper-bot/electron/main.cjs#L1131-L1137 reads count + results[]; the
    table also reads avg_rating/card_url/website, which /api/businesses does
    not return — it renders "no ratings yet" and no link (in-repo, no issue)."""
    r = client.get("/api/businesses", params={"category": "café", "limit": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == len(data["results"]) >= 2
    for row in data["results"]:
        assert {"name", "category", "review_count", "distance_km"} <= row.keys()

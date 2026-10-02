"""Issue #8 (E4): public read boundary — cache, rate limit, correlation.

The boundary must never change WHAT a route answers: same order, same
fallback, same body. These tests pin cache eligibility, TTL, invalidation,
bypass, stale-on-error, invalid input, rate limiting, CORS and no-store.
"""
import pytest
from fastapi.testclient import TestClient

from models import Business, Review, User
from services import edge_boundary
from tests.conftest import sample_deal_payload, signed_post

ORIGIN = "https://localloop.ai"


@pytest.fixture(autouse=True)
def fresh_boundary(monkeypatch):
    edge_boundary.read_cache.clear()
    edge_boundary.rate_limiter.clear()
    for name in ("LOOPER_READ_CACHE_TTL_S", "LOOPER_READ_CACHE_STALE_S",
                 "LOOPER_READ_RATE_LIMIT_PER_MIN", "LOOPER_CLIENT_IP_HEADER",
                 "TYPEDB_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    yield
    edge_boundary.read_cache.clear()
    edge_boundary.rate_limiter.clear()


@pytest.fixture()
def cache_on(monkeypatch):
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "30")
    monkeypatch.setenv("LOOPER_READ_CACHE_STALE_S", "60")


@pytest.fixture()
def clock(monkeypatch):
    """Controllable monotonic clock for TTL/stale tests."""
    now = {"t": 1000.0}
    monkeypatch.setattr(edge_boundary.time, "monotonic", lambda: now["t"])
    return now


def _seed(db):
    """Three Bondi cafés: reviews decide the order, one gets a huge deal."""
    user = User(first_name="Tester", mobile_number="0400000099")
    db.add(user)
    a = Business(name="Cafe Alpha", category="café", suburb="Bondi",
                 lat=-33.8908, lng=151.2748, source="manual")
    b = Business(name="Cafe Beta", category="café", suburb="Bondi",
                 lat=-33.8910, lng=151.2750, source="manual")
    db.add_all([a, b])
    db.flush()
    for i in range(3):
        db.add(Review(business_id=a.id, user_id=user.id, rating=5,
                      review_text=f"Lovely coffee and friendly staff, visit {i}"))
    db.add(Review(business_id=b.id, user_id=user.id, rating=4,
                  review_text="Good flat white, will come back"))
    db.commit()
    return a, b


def _search(client, **params):
    return client.get("/api/search", params={"q": "café", **params})


# ---- defaults: nothing changes until the owner flips a flag ----------------

def test_defaults_are_off_and_answer_is_unchanged(client, db):
    _seed(db)
    first = _search(client)
    second = _search(client)
    assert first.status_code == second.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert "x-looper-cache" not in first.headers
    assert first.json() == second.json()
    for _ in range(50):  # no rate limit by default
        assert _search(client).status_code == 200


def test_request_id_echoed_or_generated(client, db):
    good = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert good.headers["x-request-id"] == "trace-abc-12345"
    bad = client.get("/health", headers={"X-Request-ID": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"
    assert len(bad.headers["x-request-id"]) == 32


# ---- hit / miss / key -------------------------------------------------------

def test_cache_miss_then_hit_same_body(client, db, cache_on):
    _seed(db)
    miss = _search(client)
    hit = _search(client)
    assert miss.headers["x-looper-cache"] == "MISS"
    assert hit.headers["x-looper-cache"] == "HIT"
    assert hit.json() == miss.json()
    assert hit.headers["cache-control"].startswith("public, max-age=0, s-maxage=30")


def test_key_ignores_telemetry_and_unknown_params(client, db, cache_on):
    _seed(db)
    assert _search(client, session="s-1", intent="search").headers["x-looper-cache"] == "MISS"
    assert _search(client, session="s-2", intent="voice").headers["x-looper-cache"] == "HIT"
    assert _search(client, utm_source="fb").headers["x-looper-cache"] == "HIT"


def test_key_includes_every_ranking_param(client, db, cache_on):
    _seed(db)
    _search(client)
    for extra in ({"lat": "-33.89"}, {"lng": "151.27"}, {"radius_km": "9"},
                  {"category": "café"}, {"limit": "2"}):
        assert _search(client, **extra).headers["x-looper-cache"] == "MISS", extra
    assert client.get("/api/search", params={"q": "coffee"}).headers["x-looper-cache"] == "MISS"


def test_key_params_are_ranking_inputs_only():
    banned = {"session", "intent", "discount", "discount_size", "source", "rank_boost",
              "card_url", "payment", "tier", "user_id", "mobile", "email"}
    for path, params in edge_boundary.CACHEABLE_PARAMS.items():
        assert not banned & set(params), path


# ---- TTL / invalidation / bypass / stale -------------------------------------

def test_ttl_expiry(client, db, cache_on, clock):
    _seed(db)
    _search(client)
    clock["t"] += 29
    assert _search(client).headers["x-looper-cache"] == "HIT"
    clock["t"] += 2
    assert _search(client).headers["x-looper-cache"] == "MISS"


def test_successful_write_invalidates(client, db, cache_on):
    _seed(db)
    before = _search(client).json()
    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(business_name="Cafe Gamma"))
    assert resp.status_code == 200
    after = _search(client)
    assert after.headers["x-looper-cache"] == "MISS"
    assert "Cafe Gamma" in [r["name"] for r in after.json()["results"]]
    assert "Cafe Gamma" not in [r["name"] for r in before["results"]]


def test_rejected_write_does_not_invalidate(client, db, cache_on):
    _seed(db)
    _search(client)
    resp = signed_post(client, "/api/ingest/hybridcard-deal", sample_deal_payload(), tamper=True)
    assert resp.status_code == 401
    assert _search(client).headers["x-looper-cache"] == "HIT"


def test_no_cache_request_revalidates(client, db, cache_on):
    _seed(db)
    _search(client)
    fresh = client.get("/api/search", params={"q": "café"}, headers={"Cache-Control": "no-cache"})
    assert fresh.headers["x-looper-cache"] == "MISS"
    assert _search(client).headers["x-looper-cache"] == "HIT"


def test_authorization_bypasses_and_is_never_stored(client, db, cache_on):
    _seed(db)
    resp = client.get("/api/search", params={"q": "café"}, headers={"Authorization": "Bearer x"})
    assert resp.headers["x-looper-cache"] == "BYPASS"
    assert resp.headers["cache-control"] == "no-store"
    assert _search(client).headers["x-looper-cache"] == "MISS"


def test_stale_served_when_route_errors(db, cache_on, clock, monkeypatch):
    from main import app
    import routes.search
    _seed(db)
    client = TestClient(app, raise_server_exceptions=False)
    good = _search(client).json()
    clock["t"] += 45  # past TTL, inside the stale window

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(routes.search, "get_top_review", boom)
    stale = _search(client)
    assert stale.status_code == 200
    assert stale.headers["x-looper-cache"] == "STALE"
    assert stale.json() == good

    clock["t"] += 60  # beyond ttl + stale: the error surfaces honestly
    assert _search(client).status_code == 500


def test_invalid_input_never_cached(client, db, cache_on):
    for _ in range(2):
        resp = client.get("/api/search")  # q is required
        assert resp.status_code == 422
        assert resp.headers["x-looper-cache"] == "MISS"
        assert resp.headers["cache-control"] == "no-store"
    bad = client.get("/api/discover", params={"radius_km": "999"})
    assert bad.status_code == 422
    assert not edge_boundary.read_cache._entries


# ---- anti-bias + fallback parity through the cache ---------------------------

def test_cached_order_equals_uncached_and_ignores_discount(client, db, cache_on):
    _seed(db)
    resp = signed_post(client, "/api/ingest/hybridcard-deal",
                       sample_deal_payload(business_name="Discount Cafe", discount_size=90,
                                           rank_boost=True))
    assert resp.status_code == 200
    miss = _search(client, lat="-33.8908", lng="151.2748")
    hit = _search(client, lat="-33.8908", lng="151.2748")
    assert hit.headers["x-looper-cache"] == "HIT"
    names = [r["name"] for r in hit.json()["results"]]
    assert names == [r["name"] for r in miss.json()["results"]]
    assert names.index("Cafe Alpha") < names.index("Cafe Beta") < names.index("Discount Cafe")
    assert len(names) >= 2  # several options, never a single "best"


def test_discover_typedb_unavailable_fallback_parity(client, db, cache_on, monkeypatch):
    import routes.discover
    _seed(db)
    baseline = client.get("/api/discover", params={"suburb": "Bondi"}).json()
    assert baseline["engine"] == "fallback"

    def graph_down(*a, **k):
        raise ConnectionError("typedb unreachable")

    monkeypatch.setattr(routes.discover, "_graph_discover", graph_down)
    monkeypatch.setenv("TYPEDB_ENABLED", "true")
    miss = client.get("/api/discover", params={"suburb": "Bondi"})
    hit = client.get("/api/discover", params={"suburb": "Bondi"})
    assert miss.headers["x-looper-cache"] == "MISS"  # engine switch is part of the key
    assert hit.headers["x-looper-cache"] == "HIT"
    assert miss.json() == hit.json() == baseline
    assert [r["name"] for r in hit.json()["results"]] == ["Cafe Alpha", "Cafe Beta"]


# ---- rate limit ---------------------------------------------------------------

def test_rate_limit_429_with_retry_after_and_cors(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_RATE_LIMIT_PER_MIN", "3")
    for _ in range(3):
        assert _search(client).status_code == 200
    limited = client.get("/api/search", params={"q": "café"}, headers={"Origin": ORIGIN})
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.headers["access-control-allow-origin"] == ORIGIN
    assert limited.headers["cache-control"] == "no-store"
    # writes and health are outside the read limiter
    assert client.get("/health").status_code == 200
    resp = signed_post(client, "/api/ingest/hybridcard-deal", sample_deal_payload())
    assert resp.status_code == 200


def test_rate_limit_keys_on_trusted_header_only(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_RATE_LIMIT_PER_MIN", "1")
    spoof = {"CF-Connecting-IP": "203.0.113.1"}
    assert _search(client).status_code == 200
    # header NOT trusted: same peer, same bucket, spoofing does not help
    assert client.get("/api/search", params={"q": "café"}, headers=spoof).status_code == 429

    edge_boundary.rate_limiter.clear()
    monkeypatch.setenv("LOOPER_CLIENT_IP_HEADER", "cf-connecting-ip")
    assert client.get("/api/search", params={"q": "café"}, headers=spoof).status_code == 200
    assert client.get("/api/search", params={"q": "café"},
                      headers={"CF-Connecting-IP": "203.0.113.2"}).status_code == 200
    assert client.get("/api/search", params={"q": "café"}, headers=spoof).status_code == 429


# ---- CORS + no-store ------------------------------------------------------------

def test_cors_headers_on_cache_hit(client, db, cache_on):
    _seed(db)
    _search(client)
    hit = client.get("/api/search", params={"q": "café"}, headers={"Origin": ORIGIN})
    assert hit.headers["x-looper-cache"] == "HIT"
    assert hit.headers["access-control-allow-origin"] == ORIGIN
    assert "x-request-id" in hit.headers["access-control-expose-headers"].lower()
    other = client.get("/api/search", params={"q": "café"}, headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_preflight_untouched(client, db, cache_on, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_RATE_LIMIT_PER_MIN", "1")
    for _ in range(3):
        resp = client.options("/api/search", headers={
            "Origin": ORIGIN, "Access-Control-Request-Method": "GET"})
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.parametrize("path", ["/api/users/1", "/api/code/ABC123", "/api/reviews/1",
                                  "/api/ingest/status", "/health"])
def test_private_and_operational_reads_are_no_store(client, db, cache_on, path):
    first = client.get(path)
    second = client.get(path)
    assert first.headers["cache-control"] == "no-store"
    assert "x-looper-cache" not in second.headers


def test_review_reads_never_served_from_cache(client, db, cache_on):
    a, _ = _seed(db)
    before = client.get(f"/api/reviews/{a.id}").json()["total_reviews"]
    user = User(first_name="Second", mobile_number="0400000098")
    db.add(user)
    db.flush()
    db.add(Review(business_id=a.id, user_id=user.id, rating=5, review_text="Another fine visit here"))
    db.commit()
    assert client.get(f"/api/reviews/{a.id}").json()["total_reviews"] == before + 1

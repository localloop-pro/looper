from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient

from main import app
from routes import identity as identity_route
from services.kaspa_identity import EXPECTED_IDENTITIES, KaspaIdentityVerifier, normalize_domain


NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def provider_payload(domain="localloop.kas", **overrides):
    expected = EXPECTED_IDENTITIES[domain]
    asset = {
        "id": str(expected.inscription_number), "assetId": expected.asset_id,
        "asset": domain, "owner": expected.owner_address, "status": "default",
        "transactionId": expected.transaction_id, "isDomain": True, "isVerifiedDomain": True,
    }
    asset.update(overrides)
    return {"success": True, "data": {"assets": [asset]}}


def verifier_for(tmp_path, handler, clock=lambda: NOW):
    return KaspaIdentityVerifier(cache_path=tmp_path / "identity.json", transport=httpx.MockTransport(handler),
                                 ttl_seconds=60, stale_seconds=300, clock=clock)


def test_domain_normalization_is_allowlisted():
    assert normalize_domain("  LOCALLOOP.KAS ") == "localloop.kas"
    for invalid in ("unknown.kas", "localloop.kas.example", "ⅼocalloop.kas"):
        try:
            normalize_domain(invalid)
            assert False, f"accepted {invalid}"
        except ValueError:
            pass


def test_fresh_verification_keeps_asset_and_transaction_ids_distinct(tmp_path):
    service = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    result = service.verify("localloop.kas")
    assert result["verificationState"] == "fresh"
    assert result["assetId"].endswith("i0")
    assert result["transactionId"] + "i0" == result["assetId"]
    assert result["verifiedAt"] == "2026-09-01T00:00:00Z"


def test_mismatch_never_falls_back_to_cached_verified_state(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    bad = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload(owner="kaspa:attacker")),
                       clock=lambda: NOW + timedelta(seconds=61))
    assert bad.verify("localloop.kas")["verificationState"] == "mismatch"


def test_provider_failure_uses_bounded_stale_cache_then_unavailable(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    good.verify("localloop.kas")
    failed = lambda request: httpx.Response(429, json={"error": "rate limited"})
    stale = verifier_for(tmp_path, failed, clock=lambda: NOW + timedelta(seconds=61))
    unavailable = verifier_for(tmp_path, failed, clock=lambda: NOW + timedelta(seconds=301))
    assert stale.verify("localloop.kas")["verificationState"] == "stale"
    assert unavailable.verify("localloop.kas")["verificationState"] == "unavailable"


def test_malformed_provider_payload_is_unavailable(tmp_path):
    service = verifier_for(tmp_path, lambda request: httpx.Response(200, json={"data": {"assets": "bad"}}))
    assert service.verify("qikflo.kas")["verificationState"] == "unavailable"


def test_public_contract_and_unknown_domain(tmp_path, monkeypatch):
    def handler(request):
        domain = request.url.params["asset"]
        return httpx.Response(200, json=provider_payload(domain))
    service = verifier_for(tmp_path, handler)
    monkeypatch.setattr(identity_route, "verifier", service)
    client = TestClient(app)
    response = client.get("/api/identity/domains")
    assert response.status_code == 200
    assert [item["domain"] for item in response.json()["domains"]] == ["localloop.kas", "qikflo.kas"]
    item = client.get("/api/identity/domains/LOCALLOOP.KAS")
    assert item.status_code == 200
    assert set(item.json()) == {"domain", "network", "assetId", "inscriptionNumber", "transactionId",
                                "ownerAddress", "status", "verificationState", "verifiedAt", "expiresAt", "explorerUrl"}
    assert client.get("/api/identity/domains/attacker.kas").status_code == 404

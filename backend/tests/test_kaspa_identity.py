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


def test_invalid_json_and_timeout_are_unavailable(tmp_path):
    invalid = verifier_for(tmp_path, lambda request: httpx.Response(200, content=b"not-json"))
    assert invalid.verify("qikflo.kas")["verificationState"] == "unavailable"
    def timeout(_request):
        raise httpx.ReadTimeout("timed out")
    timed_out = verifier_for(tmp_path / "timeout", timeout)
    assert timed_out.verify("qikflo.kas")["verificationState"] == "unavailable"


def test_tampered_future_cache_is_rejected(tmp_path):
    cache_path = tmp_path / "identity.json"
    cache_path.write_text('{"localloop.kas":{"verifiedAt":"2099-01-01T00:00:00Z","expiresAt":"2099-01-01T01:00:00Z","staleUntil":"2099-01-02T00:00:00Z","provider":"kns-mainnet-v1"}}')
    service = KaspaIdentityVerifier(cache_path=cache_path,
        transport=httpx.MockTransport(lambda request: httpx.Response(503)), clock=lambda: NOW)
    assert service.verify("localloop.kas")["verificationState"] == "unavailable"


def test_provider_recovers_from_unavailable_to_fresh(tmp_path):
    attempts = {"count": 0}
    def handler(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": "maintenance"})
        return httpx.Response(200, json=provider_payload())
    service = verifier_for(tmp_path, handler)
    assert service.verify("localloop.kas", force=True)["verificationState"] == "unavailable"
    assert service.verify("localloop.kas", force=True)["verificationState"] == "fresh"


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


# ── review round (Codex) ─────────────────────────────────────────────────

def test_malformed_nested_data_member_is_unavailable_not_500(tmp_path):
    for index, payload in enumerate(({"data": None}, {"data": []}, {"data": "x"}, {"success": True})):
        service = verifier_for(tmp_path / f"case-{index}", lambda request, body=payload: httpx.Response(200, json=body))
        assert service.verify("qikflo.kas")["verificationState"] == "unavailable"


def test_mismatch_tombstones_cache_so_a_later_failure_is_unavailable(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    bad = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload(owner="kaspa:attacker")),
                       clock=lambda: NOW + timedelta(seconds=61))
    assert bad.verify("localloop.kas")["verificationState"] == "mismatch"
    # Still inside the old stale window — must NOT report "stale"/previously verified.
    failing = verifier_for(tmp_path, lambda request: httpx.Response(503), clock=lambda: NOW + timedelta(seconds=62))
    assert failing.verify("localloop.kas")["verificationState"] == "unavailable"


def test_cache_is_bound_to_provider_url_and_expected_identity(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    reconfigured = KaspaIdentityVerifier(
        provider_url="https://mock.example/kns", cache_path=tmp_path / "identity.json",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
        ttl_seconds=60, stale_seconds=300, clock=lambda: NOW + timedelta(seconds=1))
    # The surviving entry verified a different provider configuration: rejected,
    # so neither "fresh" nor "stale" can be claimed for it.
    assert reconfigured.verify("localloop.kas")["verificationState"] == "unavailable"


def test_unwritable_cache_is_best_effort_and_still_verifies(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    service = KaspaIdentityVerifier(
        cache_path=blocker / "cache.json",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=provider_payload())),
        ttl_seconds=60, stale_seconds=300, clock=lambda: NOW)
    assert service.verify("localloop.kas")["verificationState"] == "fresh"


def test_provider_failures_are_negatively_cached_with_backoff(tmp_path):
    attempts = {"count": 0}
    current = {"now": NOW}

    def handler(_request):
        attempts["count"] += 1
        return httpx.Response(503)

    service = KaspaIdentityVerifier(cache_path=tmp_path / "identity.json", transport=httpx.MockTransport(handler),
                                    ttl_seconds=60, stale_seconds=300, failure_backoff_seconds=30,
                                    clock=lambda: current["now"])
    assert service.verify("localloop.kas")["verificationState"] == "unavailable"
    assert service.verify("localloop.kas")["verificationState"] == "unavailable"
    assert attempts["count"] == 1  # second call served from the failure cache
    current["now"] = NOW + timedelta(seconds=31)
    assert service.verify("localloop.kas")["verificationState"] == "unavailable"
    assert attempts["count"] == 2  # backoff elapsed → one more upstream attempt


def test_concurrent_refreshes_share_one_provider_request(tmp_path):
    import threading

    attempts = {"count": 0}
    started = threading.Event()
    release = threading.Event()

    def handler(_request):
        attempts["count"] += 1
        started.set()
        release.wait(5)
        return httpx.Response(200, json=provider_payload())

    service = verifier_for(tmp_path, handler)
    results: dict[str, dict] = {}
    first = threading.Thread(target=lambda: results.__setitem__("leader", service.verify("localloop.kas")))
    first.start()
    assert started.wait(5)
    # A second caller must NOT park behind the in-flight refresh: it gets the
    # bounded answer immediately (cold cache → unavailable) while the leader
    # is still blocked in the provider call.
    second = threading.Thread(target=lambda: results.__setitem__("follower", service.verify("localloop.kas")))
    second.start()
    second.join(2)
    assert not second.is_alive()
    assert results["follower"]["verificationState"] == "unavailable"
    release.set()
    first.join(5)
    assert attempts["count"] == 1
    assert results["leader"]["verificationState"] == "fresh"
    # Once the leader has written the cache, callers are served fresh from it.
    assert service.verify("localloop.kas")["verificationState"] == "fresh"
    assert attempts["count"] == 1


def test_empty_successful_lookup_is_mismatch_and_tombstones(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    # The provider authoritatively has NO record now: that is a mismatch, and it
    # must not be masked by the still-valid stale window.
    gone = verifier_for(tmp_path, lambda request: httpx.Response(200, json={"success": True, "data": {"assets": []}}),
                        clock=lambda: NOW + timedelta(seconds=61))
    assert gone.verify("localloop.kas")["verificationState"] == "mismatch"
    failing = verifier_for(tmp_path, lambda request: httpx.Response(503), clock=lambda: NOW + timedelta(seconds=62))
    assert failing.verify("localloop.kas")["verificationState"] == "unavailable"


def test_mismatch_is_shared_across_callers_for_the_backoff_window(tmp_path):
    attempts = {"count": 0}
    current = {"now": NOW}

    def handler(_request):
        attempts["count"] += 1
        return httpx.Response(200, json=provider_payload(owner="kaspa:attacker"))

    service = KaspaIdentityVerifier(cache_path=tmp_path / "identity.json", transport=httpx.MockTransport(handler),
                                    ttl_seconds=60, stale_seconds=300, failure_backoff_seconds=30,
                                    clock=lambda: current["now"])
    for _ in range(3):
        assert service.verify("localloop.kas")["verificationState"] == "mismatch"
    assert attempts["count"] == 1  # one upstream fetch serves the whole window
    current["now"] = NOW + timedelta(seconds=31)
    assert service.verify("localloop.kas")["verificationState"] == "mismatch"
    assert attempts["count"] == 2


def test_in_memory_tombstone_holds_when_the_cache_cannot_be_rewritten(tmp_path):
    import os
    import stat

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    responses = {"body": provider_payload()}
    current = {"now": NOW}

    def handler(_request):
        body = responses["body"]
        return httpx.Response(200, json=body) if body is not None else httpx.Response(503)

    service = KaspaIdentityVerifier(cache_path=cache_dir / "identity.json", transport=httpx.MockTransport(handler),
                                    ttl_seconds=60, stale_seconds=300, clock=lambda: current["now"])
    assert service.verify("localloop.kas")["verificationState"] == "fresh"
    os.chmod(cache_dir, stat.S_IRUSR | stat.S_IXUSR)  # readable, not writable → disk tombstone fails
    try:
        current["now"] = NOW + timedelta(seconds=61)
        responses["body"] = provider_payload(owner="kaspa:attacker")
        assert service.verify("localloop.kas")["verificationState"] == "mismatch"
        current["now"] = NOW + timedelta(seconds=120)  # past the mismatch backoff, inside staleUntil
        responses["body"] = None
        assert service.verify("localloop.kas")["verificationState"] == "unavailable"
    finally:
        os.chmod(cache_dir, stat.S_IRWXU)


def test_non_string_cache_timestamps_are_rejected_not_500(tmp_path):
    cache_path = tmp_path / "identity.json"
    cache_path.write_text('{"localloop.kas":{"verifiedAt":1725148800,"expiresAt":["x"],"staleUntil":{},"provider":"kns-mainnet-v1"}}')
    service = KaspaIdentityVerifier(cache_path=cache_path,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=provider_payload())),
        ttl_seconds=60, stale_seconds=300, clock=lambda: NOW)
    assert service.verify("localloop.kas")["verificationState"] == "fresh"


def test_unsuccessful_envelope_is_a_provider_failure_not_a_mismatch(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    # HTTP 200 with success:false and an empty asset set is an error payload —
    # it must NOT tombstone the valid cache; the bounded stale answer applies.
    error_payload = {"success": False, "error": "upstream", "data": {"assets": []}}
    failing = verifier_for(tmp_path, lambda request: httpx.Response(200, json=error_payload),
                           clock=lambda: NOW + timedelta(seconds=61))
    assert failing.verify("localloop.kas")["verificationState"] == "stale"


def test_fractional_or_boolean_inscription_ids_never_match(tmp_path):
    for index, bad_id in enumerate((47164.5, True, "47164.0", "0x b83c", None)):
        service = verifier_for(tmp_path / f"id-{index}", lambda request, v=bad_id: httpx.Response(200, json=provider_payload(id=v)))
        assert service.verify("localloop.kas")["verificationState"] == "mismatch", bad_id
    exact_int = verifier_for(tmp_path / "int", lambda request: httpx.Response(200, json=provider_payload(id=47164)))
    assert exact_int.verify("localloop.kas")["verificationState"] == "fresh"


def test_ambiguous_asset_set_is_a_mismatch_not_an_outage(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    exact = provider_payload()["data"]["assets"][0]
    reissued = dict(exact, owner="kaspa:attacker", id="99999")
    two = {"success": True, "data": {"assets": [exact, reissued]}}
    ambiguous = verifier_for(tmp_path, lambda request: httpx.Response(200, json=two),
                             clock=lambda: NOW + timedelta(seconds=61))
    # The exact record is present but not unique → identity cannot be established.
    assert ambiguous.verify("localloop.kas")["verificationState"] == "mismatch"
    duplicated = {"success": True, "data": {"assets": [exact, dict(exact)]}}
    assert verifier_for(tmp_path / "dup", lambda request: httpx.Response(200, json=duplicated)
                        ).verify("localloop.kas")["verificationState"] == "mismatch"
    # And the tombstone holds: a later outage is unavailable, not stale.
    failing = verifier_for(tmp_path, lambda request: httpx.Response(503), clock=lambda: NOW + timedelta(seconds=62))
    assert failing.verify("localloop.kas")["verificationState"] == "unavailable"


def test_stale_window_is_judged_after_provider_io_not_before(tmp_path):
    good = verifier_for(tmp_path, lambda request: httpx.Response(200, json=provider_payload()))
    assert good.verify("localloop.kas")["verificationState"] == "fresh"
    current = {"now": NOW + timedelta(seconds=299)}  # refresh starts 1s before staleUntil

    def slow_failure(_request):
        current["now"] = NOW + timedelta(seconds=305)  # ...and the provider answers after it
        return httpx.Response(503)

    service = KaspaIdentityVerifier(cache_path=tmp_path / "identity.json", transport=httpx.MockTransport(slow_failure),
                                    ttl_seconds=60, stale_seconds=300, clock=lambda: current["now"])
    assert service.verify("localloop.kas")["verificationState"] == "unavailable"

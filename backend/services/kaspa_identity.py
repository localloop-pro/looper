"""Read-only verification of LocalLoop's configured KNS organization identities."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import httpx

LOGGER = logging.getLogger("looper.kaspa_identity")
PROVIDER = "kns-mainnet-v1"
DEFAULT_PROVIDER_URL = "https://api.knsdomains.org/mainnet"
DEFAULT_TTL_SECONDS = 3600
DEFAULT_STALE_SECONDS = 86400
EXPECTED_OWNER = "kaspa:qrs4ss39sycutun733g8rm90k284wqc7nneucp6t3mls3tm83d49cjyc3hwew"


@dataclass(frozen=True)
class ExpectedIdentity:
    domain: str
    asset_id: str
    inscription_number: int
    transaction_id: str
    owner_address: str = EXPECTED_OWNER
    status: str = "default"
    network: str = "mainnet"


EXPECTED_IDENTITIES = {
    "localloop.kas": ExpectedIdentity(
        domain="localloop.kas",
        inscription_number=47164,
        asset_id="4f1596dcade19b2c97d0a8e8e3c6fe894bfef5de808de88fc54c8d9f8a5df01bi0",
        transaction_id="4f1596dcade19b2c97d0a8e8e3c6fe894bfef5de808de88fc54c8d9f8a5df01b",
    ),
    "qikflo.kas": ExpectedIdentity(
        domain="qikflo.kas",
        inscription_number=47165,
        asset_id="e9d61f8dcc3ea925a6dbd1eb8ba328d45ed0bf3a59c1ca373aacf0918a69ddfci0",
        transaction_id="e9d61f8dcc3ea925a6dbd1eb8ba328d45ed0bf3a59c1ca373aacf0918a69ddfc",
    ),
}


class IdentityProviderError(RuntimeError):
    """Safe provider failure marker; raw upstream errors stay server-side."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_domain(value: str) -> str:
    if any(ord(char) > 127 for char in value):
        raise ValueError("organization domains must be ASCII")
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    if not normalized or len(normalized) > 253 or normalized not in EXPECTED_IDENTITIES:
        raise ValueError("unknown organization domain")
    return normalized


def public_record(expected: ExpectedIdentity, state: str, verified_at: str | None = None,
                  expires_at: str | None = None) -> dict[str, Any]:
    return {
        "domain": expected.domain,
        "network": expected.network,
        "assetId": expected.asset_id,
        "inscriptionNumber": expected.inscription_number,
        "transactionId": expected.transaction_id,
        "ownerAddress": expected.owner_address,
        "status": expected.status,
        "verificationState": state,
        "verifiedAt": verified_at,
        "expiresAt": expires_at,
        "explorerUrl": f"https://kas.fyi/transaction/{expected.transaction_id}",
    }


class KaspaIdentityVerifier:
    def __init__(self, *, provider_url: str | None = None, cache_path: str | Path | None = None,
                 ttl_seconds: int | None = None, stale_seconds: int | None = None,
                 transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], datetime] = utc_now):
        self.provider_url = (provider_url or os.getenv("KNS_API_BASE_URL") or DEFAULT_PROVIDER_URL).rstrip("/")
        if self.provider_url != DEFAULT_PROVIDER_URL:
            LOGGER.warning(json.dumps({"event": "kaspa_identity.provider_override", "provider": self.provider_url}))
        default_cache = Path(__file__).resolve().parents[1] / "data" / "kaspa_identity_cache.json"
        self.cache_path = Path(cache_path or os.getenv("KASPA_IDENTITY_CACHE_PATH") or default_cache)
        self.ttl = int(ttl_seconds or os.getenv("KASPA_IDENTITY_TTL_SECONDS") or DEFAULT_TTL_SECONDS)
        self.stale_window = int(stale_seconds or os.getenv("KASPA_IDENTITY_STALE_SECONDS") or DEFAULT_STALE_SECONDS)
        self.transport = transport
        self.clock = clock
        self._lock = threading.Lock()

    def _read_cache(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (FileNotFoundError, OSError, ValueError):
            return {}

    def _write_cache(self, cache: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")
        temporary.replace(self.cache_path)

    def _fetch(self, expected: ExpectedIdentity) -> tuple[dict[str, Any], str]:
        url = f"{self.provider_url}/api/v1/assets"
        try:
            with httpx.Client(transport=self.transport, timeout=8.0, follow_redirects=False,
                              headers={"Accept": "application/json", "User-Agent": "LocalLoop-Identity-Verifier/1.0"}) as client:
                response = client.get(url, params={"asset": expected.domain, "page": 1, "pageSize": 5})
            if response.status_code != 200:
                raise IdentityProviderError(f"provider status {response.status_code}")
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IdentityProviderError("provider request failed") from exc
        raw_hash = hashlib.sha256(response.content).hexdigest()
        assets = payload.get("data", {}).get("assets") if isinstance(payload, dict) else None
        if not isinstance(assets, list) or len(assets) != 1 or not isinstance(assets[0], dict):
            raise IdentityProviderError("provider returned an unexpected asset set")
        return assets[0], raw_hash

    @staticmethod
    def _matches(expected: ExpectedIdentity, asset: dict[str, Any]) -> bool:
        try:
            return (
                str(asset["asset"]).strip().lower() == expected.domain
                and str(asset["assetId"]) == expected.asset_id
                and int(asset["id"]) == expected.inscription_number
                and str(asset["transactionId"]) == expected.transaction_id
                and str(asset["owner"]) == expected.owner_address
                and str(asset["status"]).strip().lower() == expected.status
                and asset.get("isDomain") is True
                and asset.get("isVerifiedDomain") is True
            )
        except (KeyError, TypeError, ValueError):
            return False

    def verify(self, domain: str, *, force: bool = False) -> dict[str, Any]:
        normalized = normalize_domain(domain)
        expected = EXPECTED_IDENTITIES[normalized]
        now = self.clock()
        with self._lock:
            cache = self._read_cache()
            cached = cache.get(normalized) if isinstance(cache.get(normalized), dict) else None
            if cached and not force:
                try:
                    if now < parse_time(cached["expiresAt"]):
                        return public_record(expected, "fresh", cached["verifiedAt"], cached["expiresAt"])
                except (KeyError, TypeError, ValueError):
                    cached = None

            try:
                asset, raw_hash = self._fetch(expected)
                if not self._matches(expected, asset):
                    LOGGER.error(json.dumps({"event": "kaspa_identity.mismatch", "domain": normalized,
                                             "observedOwner": str(asset.get("owner", ""))[:80]}))
                    return public_record(expected, "mismatch")
                expires = now + timedelta(seconds=self.ttl)
                cache[normalized] = {
                    "verifiedAt": isoformat(now), "expiresAt": isoformat(expires),
                    "staleUntil": isoformat(now + timedelta(seconds=self.stale_window)),
                    "provider": PROVIDER, "rawResponseHash": raw_hash,
                }
                self._write_cache(cache)
                LOGGER.info(json.dumps({"event": "kaspa_identity.verified", "domain": normalized, "provider": PROVIDER}))
                return public_record(expected, "fresh", isoformat(now), isoformat(expires))
            except IdentityProviderError:
                LOGGER.warning(json.dumps({"event": "kaspa_identity.provider_failure", "domain": normalized,
                                           "provider": PROVIDER}))
                if cached:
                    try:
                        if now < parse_time(cached["staleUntil"]):
                            return public_record(expected, "stale", cached["verifiedAt"], cached["expiresAt"])
                    except (KeyError, TypeError, ValueError):
                        pass
                return public_record(expected, "unavailable")

    def list_domains(self, *, force: bool = False) -> list[dict[str, Any]]:
        return [self.verify(domain, force=force) for domain in EXPECTED_IDENTITIES]

    def health(self) -> dict[str, Any]:
        domains = self.list_domains()
        states = {item["domain"]: item["verificationState"] for item in domains}
        return {
            "status": "healthy" if all(state == "fresh" for state in states.values()) else "degraded",
            "provider": PROVIDER,
            "domains": states,
        }


verifier = KaspaIdentityVerifier()

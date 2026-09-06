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

import httpx

LOGGER = logging.getLogger("looper.kaspa_identity")
PROVIDER = "kns-mainnet-v1"
DEFAULT_PROVIDER_URL = "https://api.knsdomains.org/mainnet"
DEFAULT_TTL_SECONDS = 3600
DEFAULT_STALE_SECONDS = 86400
# After a provider failure, callers get the bounded stale/unavailable answer
# straight from cache for this long instead of each re-hitting the provider.
DEFAULT_FAILURE_BACKOFF_SECONDS = 30
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


def parse_time(value: Any) -> datetime:
    # Corrupt/hand-edited caches may hold numbers, lists or objects here; that is
    # an invalid entry, never a 500 (review P2).
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


class KaspaIdentityVerifier:
    """Verifies the configured identities against the KNS provider.

    Locking model (review P1): ``self._lock`` guards only in-memory state and the
    cache file, never provider I/O. One request per domain (the leader) performs
    the provider refresh under a per-domain lock acquired WITHOUT blocking;
    every other request for that domain returns the bounded cached/unavailable
    state immediately instead of parking a worker thread behind the refresh.
    Provider failures and authoritative mismatches are negatively cached for
    ``failure_backoff`` seconds so a burst during an outage or a security event
    produces one upstream request, not one per caller.
    """

    def __init__(self, *, provider_url: str | None = None, cache_path: str | Path | None = None,
                 ttl_seconds: int | None = None, stale_seconds: int | None = None,
                 failure_backoff_seconds: int | None = None,
                 transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], datetime] = utc_now):
        self.provider_url = (provider_url or os.getenv("KNS_API_BASE_URL") or DEFAULT_PROVIDER_URL).rstrip("/")
        if self.provider_url != DEFAULT_PROVIDER_URL:
            LOGGER.warning(json.dumps({"event": "kaspa_identity.provider_override", "provider": self.provider_url}))
        # Docker deployments point this at the persistent volume via
        # KASPA_IDENTITY_CACHE_PATH (see docker-compose.yml); this default is only
        # correct for a plain checkout.
        default_cache = Path(__file__).resolve().parents[1] / "data" / "kaspa_identity_cache.json"
        self.cache_path = Path(cache_path or os.getenv("KASPA_IDENTITY_CACHE_PATH") or default_cache)
        self.ttl = int(ttl_seconds or os.getenv("KASPA_IDENTITY_TTL_SECONDS") or DEFAULT_TTL_SECONDS)
        self.stale_window = int(stale_seconds or os.getenv("KASPA_IDENTITY_STALE_SECONDS") or DEFAULT_STALE_SECONDS)
        self.failure_backoff = (int(failure_backoff_seconds) if failure_backoff_seconds is not None
                                else _env_int("KASPA_IDENTITY_FAILURE_BACKOFF_SECONDS", DEFAULT_FAILURE_BACKOFF_SECONDS))
        self.transport = transport
        self.clock = clock
        self._lock = threading.Lock()
        self._refresh_locks: dict[str, threading.Lock] = {}
        self._failed_until: dict[str, datetime] = {}
        # Short-lived authoritative mismatch results (shared across callers).
        self._mismatch_until: dict[str, datetime] = {}
        # In-memory tombstones: a mismatch must hold even when the on-disk entry
        # cannot be deleted (read-only volume, full disk). Cleared by the next
        # successful verification.
        self._tombstoned: set[str] = set()

    # ── cache file (always under self._lock) ─────────────────────────────

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

    def _persist(self, normalized: str, entry: dict[str, Any] | None) -> None:
        """Store (or tombstone, when ``entry`` is None) one domain. Best effort on
        disk: an unwritable cache must never turn a verified identity into a 500,
        and the tombstone is kept in memory regardless of whether the disk write
        succeeds."""
        with self._lock:
            cache = self._read_cache()
            if entry is None:
                cache.pop(normalized, None)
                self._tombstoned.add(normalized)
            else:
                cache[normalized] = entry
                self._tombstoned.discard(normalized)
            try:
                self._write_cache(cache)
            except OSError as exc:
                LOGGER.warning(json.dumps({"event": "kaspa_identity.cache_write_failed", "domain": normalized,
                                           "error": exc.__class__.__name__}))

    # ── cache entries ────────────────────────────────────────────────────

    def _fingerprint(self, expected: ExpectedIdentity) -> str:
        """Binds a cache entry to the provider and the full expected identity, so a
        surviving cache file cannot vouch for a reconfigured identity."""
        material = "|".join([
            self.provider_url, expected.domain, expected.asset_id, str(expected.inscription_number),
            expected.transaction_id, expected.owner_address, expected.status, expected.network,
        ])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _cache_is_valid(self, cached: dict[str, Any], now: datetime, expected: ExpectedIdentity) -> bool:
        try:
            verified = parse_time(cached["verifiedAt"])
            expires = parse_time(cached["expiresAt"])
            stale_until = parse_time(cached["staleUntil"])
            return (
                cached.get("provider") == PROVIDER
                and cached.get("fingerprint") == self._fingerprint(expected)
                and verified <= now
                and expires == verified + timedelta(seconds=self.ttl)
                and stale_until == verified + timedelta(seconds=self.stale_window)
            )
        except (KeyError, TypeError, ValueError):
            return False

    def _read_valid_entry(self, normalized: str, expected: ExpectedIdentity, now: datetime) -> dict[str, Any] | None:
        with self._lock:
            if normalized in self._tombstoned:
                return None
            cache = self._read_cache()
        cached = cache.get(normalized)
        if not isinstance(cached, dict):
            return None
        if not self._cache_is_valid(cached, now, expected):
            LOGGER.warning(json.dumps({"event": "kaspa_identity.cache_rejected", "domain": normalized}))
            return None
        return cached

    def _refresh_lock(self, normalized: str) -> threading.Lock:
        with self._lock:
            return self._refresh_locks.setdefault(normalized, threading.Lock())

    def _failure_backoff_active(self, normalized: str, now: datetime) -> bool:
        with self._lock:
            until = self._failed_until.get(normalized)
        return until is not None and now < until

    def _note_failure(self, normalized: str, now: datetime) -> None:
        with self._lock:
            self._failed_until[normalized] = now + timedelta(seconds=self.failure_backoff)

    def _clear_failure(self, normalized: str) -> None:
        with self._lock:
            self._failed_until.pop(normalized, None)

    def _mismatch_active(self, normalized: str, now: datetime) -> bool:
        with self._lock:
            until = self._mismatch_until.get(normalized)
        return until is not None and now < until

    def _note_mismatch(self, normalized: str, now: datetime) -> None:
        with self._lock:
            self._mismatch_until[normalized] = now + timedelta(seconds=self.failure_backoff)

    def _clear_mismatch(self, normalized: str) -> None:
        with self._lock:
            self._mismatch_until.pop(normalized, None)

    # ── provider ─────────────────────────────────────────────────────────

    def _fetch(self, expected: ExpectedIdentity) -> tuple[list[dict[str, Any]], str]:
        """Returns ``(assets, raw_hash)`` for a well-formed successful envelope.
        The caller decides what the asset SET means: exactly one record is
        compared field by field; an empty set (record gone) or more than one
        record (duplicate/reissued/conflicting) is an authoritative mismatch,
        never an outage. Malformed shapes raise IdentityProviderError."""
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
        # Every nesting level is validated: a 200 whose `data` is null/list/scalar
        # is a provider fault (unavailable), never a 500 (review P2). The envelope
        # must also claim success: `success: false` with an empty/stale asset set
        # is an error payload, not an authoritative answer.
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise IdentityProviderError("provider envelope not successful")
        data = payload.get("data")
        assets = data.get("assets") if isinstance(data, dict) else None
        if not isinstance(assets, list) or not all(isinstance(item, dict) for item in assets):
            raise IdentityProviderError("provider returned an unexpected asset set")
        return assets, raw_hash

    @staticmethod
    def _exact_int(value: Any) -> int | None:
        """Only a real integer or a canonical decimal string counts; floats such
        as 47164.5 (which int() would truncate) and booleans are rejected."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    @staticmethod
    def _matches(expected: ExpectedIdentity, asset: dict[str, Any]) -> bool:
        try:
            return (
                str(asset["asset"]).strip().lower() == expected.domain
                and str(asset["assetId"]) == expected.asset_id
                and KaspaIdentityVerifier._exact_int(asset["id"]) == expected.inscription_number
                and str(asset["transactionId"]) == expected.transaction_id
                and str(asset["owner"]) == expected.owner_address
                and str(asset["status"]).strip().lower() == expected.status
                and asset.get("isDomain") is True
                and asset.get("isVerifiedDomain") is True
            )
        except (KeyError, TypeError, ValueError):
            return False

    # ── public ───────────────────────────────────────────────────────────

    @staticmethod
    def _fresh(expected: ExpectedIdentity, cached: dict[str, Any], now: datetime) -> dict[str, Any] | None:
        try:
            if now < parse_time(cached["expiresAt"]):
                return public_record(expected, "fresh", cached["verifiedAt"], cached["expiresAt"])
        except (KeyError, TypeError, ValueError):
            pass
        return None

    @staticmethod
    def _degraded(expected: ExpectedIdentity, cached: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
        if cached:
            try:
                if now < parse_time(cached["staleUntil"]):
                    return public_record(expected, "stale", cached["verifiedAt"], cached["expiresAt"])
            except (KeyError, TypeError, ValueError):
                pass
        return public_record(expected, "unavailable")

    def verify(self, domain: str, *, force: bool = False) -> dict[str, Any]:
        normalized = normalize_domain(domain)
        expected = EXPECTED_IDENTITIES[normalized]
        now = self.clock()

        cached = self._read_valid_entry(normalized, expected, now)
        if cached and not force:
            fresh = self._fresh(expected, cached, now)
            if fresh:
                return fresh
        if not force and self._mismatch_active(normalized, now):
            return public_record(expected, "mismatch")

        # One leader refreshes per domain. Everyone else gets the bounded answer
        # NOW rather than parking a FastAPI worker thread behind an 8s fetch.
        lock = self._refresh_lock(normalized)
        if not lock.acquire(blocking=False):
            return self._degraded(expected, cached, now)
        try:
            cached = self._read_valid_entry(normalized, expected, now)
            if cached and not force:
                fresh = self._fresh(expected, cached, now)
                if fresh:
                    return fresh
            if not force and self._mismatch_active(normalized, now):
                return public_record(expected, "mismatch")
            if not force and self._failure_backoff_active(normalized, now):
                return self._degraded(expected, cached, now)

            try:
                assets, raw_hash = self._fetch(expected)
            except IdentityProviderError:
                # Re-read the clock: the request may have taken seconds, and the
                # bounded stale window must be judged at decision time, not at
                # the moment the refresh started (review P2).
                after = self.clock()
                LOGGER.warning(json.dumps({"event": "kaspa_identity.provider_failure", "domain": normalized,
                                           "provider": PROVIDER}))
                self._note_failure(normalized, after)
                return self._degraded(expected, cached, after)

            after = self.clock()
            if len(assets) == 1 and self._matches(expected, assets[0]):
                asset = assets[0]
            else:
                # Authoritative mismatch: wrong fields, the record no longer
                # exists, or an ambiguous set (duplicate / reissued / conflicting
                # records) — exact identity agreement cannot be established.
                reason = "absent" if not assets else ("ambiguous" if len(assets) > 1 else "fields")
                observed = "" if len(assets) != 1 else str(assets[0].get("owner", ""))[:80]
                LOGGER.error(json.dumps({"event": "kaspa_identity.mismatch", "domain": normalized,
                                         "reason": reason, "assetCount": len(assets), "observedOwner": observed}))
                # Tombstone the cached verification so a later provider failure can
                # never resurrect "Previously verified"; share the result with every
                # caller for the backoff window instead of refetching.
                self._persist(normalized, None)
                self._note_mismatch(normalized, after)
                self._clear_failure(normalized)
                return public_record(expected, "mismatch")

            # Windows start when verification COMPLETES (`after`), not when the
            # refresh started: a slow provider call must not shorten the TTL or
            # hand back a "fresh" record whose expiresAt is already in the past.
            expires = after + timedelta(seconds=self.ttl)
            entry = {
                "verifiedAt": isoformat(after), "expiresAt": isoformat(expires),
                "staleUntil": isoformat(after + timedelta(seconds=self.stale_window)),
                "provider": PROVIDER, "rawResponseHash": raw_hash,
                "fingerprint": self._fingerprint(expected),
            }
            self._persist(normalized, entry)
            self._clear_failure(normalized)
            self._clear_mismatch(normalized)
            LOGGER.info(json.dumps({"event": "kaspa_identity.verified", "domain": normalized, "provider": PROVIDER}))
            return public_record(expected, "fresh", isoformat(after), isoformat(expires))
        finally:
            lock.release()

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

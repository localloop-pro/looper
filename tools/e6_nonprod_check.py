#!/usr/bin/env python3
"""E6 (issue #9) — load, contract and adversarial checks against a NON-production Looper.

    HYBRIDCARD_INGEST_SECRET=<the throwaway server's secret> \
      python3 tools/e6_nonprod_check.py http://127.0.0.1:8010 [--rounds 40 --workers 8]

It refuses production hosts outright and anything that is not loopback
unless you pass --non-prod-host <host> to name a staging box on purpose.
It writes bridge events (fake "E6 Check" businesses), so point it only at
a throwaway database. The secret is read from the env and never printed.

Phases:
  load        concurrent GET /api/search, /api/discover, /api/businesses
  contract    signed deal + card events, replays are duplicate:true, a stale
              retry is skipped, card_url comes back exactly as sent, the
              ingest status cockpit has no payload bodies
  adversarial tampered / expired / unknown-key signatures (401), oversized
              body (413), unsafe X-Request-IDs replaced, foreign Origin gets
              no CORS grant, open-proxy style paths are 404

Prints one JSON result; exit 1 if any check fails. Then feed the server's
trace log to tools/slo_report.py for p95/availability/bridge numbers.
Stdlib only.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

PRODUCTION_HOSTS = re.compile(
    r"(^|\.)(localloop\.ai|localloop\.pro|hybridcard\.ai|sslip\.io)$", re.I)
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
HEX32 = re.compile(r"^[0-9a-f]{32}$")


def http(method, url, *, body=None, headers=None, timeout=15):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            status, hdrs = resp.status, resp.headers
    except urllib.error.HTTPError as exc:
        data, status, hdrs = exc.read(), exc.code, exc.headers
    ms = (time.perf_counter() - started) * 1000
    try:
        parsed = json.loads(data) if data else None
    except ValueError:
        parsed = None
    return status, hdrs, parsed, ms


def sign(raw: bytes, secret: str, key_id="hc-1", ts_ms=None):
    ts = str(ts_ms if ts_ms is not None else int(time.time() * 1000))
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return {"X-HC-Signature": f"sha256={mac}", "X-HC-Key-Id": key_id,
            "X-HC-Timestamp": ts, "Content-Type": "application/json"}


class Checks:
    def __init__(self):
        self.items = []

    def add(self, phase, name, ok, detail=None):
        self.items.append({"phase": phase, "check": name, "ok": bool(ok),
                           **({"detail": detail} if detail is not None else {})})


def phase_load(base, checks, rounds, workers):
    urls = [
        f"{base}/api/search?q=caf%C3%A9&lat=-33.8908&lng=151.2748",
        f"{base}/api/search?q=hair&lat=-33.8908&lng=151.2748&radius_km=20",
        f"{base}/api/discover?suburb=Bondi",
        f"{base}/api/discover?suburb=Bronte&category=caf%C3%A9",
        f"{base}/api/businesses",
    ]
    jobs = [u for _ in range(rounds) for u in urls]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda u: http("GET", u), jobs))
    statuses = [r[0] for r in results]
    errors = sum(1 for s in statuses if s >= 500)
    ms = sorted(r[3] for r in results)
    checks.add("load", "no 5xx under concurrent reads", errors == 0,
               {"requests": len(results), "5xx": errors,
                "429": statuses.count(429), "workers": workers,
                "client_p50_ms": round(ms[len(ms) // 2], 2),
                "client_p95_ms": round(ms[max(0, -(-len(ms) * 95 // 100) - 1)], 2)})
    checks.add("load", "every response carries an X-Request-ID",
               all(r[1].get("x-request-id") for r in results))


def _deal(event_id, *, card_url, updated_at, active=True):
    return {
        "source": "hybridcard", "eventId": event_id,
        "hybrid_card_id": "card-e6-check", "deal_id": "deal-e6-check",
        "business_name": "E6 Check Cafe", "category": "café",
        "pin_type": "offering", "sub_type": "cafe", "title": "E6 check deal",
        "short_description": "non-prod release-gate check", "discount_size": 10,
        "lat": -33.8908, "lng": 151.2748, "hours": "9-5",
        "public_card_url": card_url, "active": active,
        "updated_at": updated_at, "rank_boost": False,
    }


def phase_contract(base, secret, checks):
    run = uuid.uuid4().hex[:8]
    # Path-form localhost card URL: must be stored and returned as sent.
    card_url = f"http://localhost:3000/c/e6-check-{run}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    deal = _deal(f"e6-deal-{run}", card_url=card_url, updated_at=now_iso)
    raw = json.dumps(deal).encode()
    s1, h1, b1, _ = http("POST", f"{base}/api/ingest/hybridcard-deal", body=raw,
                         headers=sign(raw, secret))
    checks.add("contract", "signed deal.upserted accepted",
               s1 == 200 and b1 == {"ok": True, "duplicate": False}, {"status": s1})
    # Replay: the sender re-signs every retry with a fresh timestamp.
    s2, _, b2, _ = http("POST", f"{base}/api/ingest/hybridcard-deal", body=raw,
                        headers=sign(raw, secret))
    checks.add("contract", "replayed eventId is idempotent (duplicate:true)",
               s2 == 200 and (b2 or {}).get("duplicate") is True, {"status": s2})

    card = {**deal, "eventId": f"e6-card-{run}", "slug": f"e6-check-{run}"}
    stale = {**card, "eventId": f"e6-card-old-{run}", "active": False,
             "updated_at": "2020-01-01T00:00:00.000Z"}
    for name, payload, want in (("card.upserted accepted", card, {"duplicate": False}),
                                ("out-of-order stale card.removed skipped", stale,
                                 {"stale": True})):
        raw_c = json.dumps(payload).encode()
        s, _, b, _ = http("POST", f"{base}/api/ingest/hybridcard-card", body=raw_c,
                          headers=sign(raw_c, secret))
        checks.add("contract", name,
                   s == 200 and all((b or {}).get(k) == v for k, v in want.items()),
                   {"status": s})

    q = urllib.parse.quote("E6 Check Cafe")
    s, _, body, _ = http("GET", f"{base}/api/search?q={q}&limit=20")
    hits = [r for r in (body or {}).get("results", []) if r.get("name") == "E6 Check Cafe"]
    checks.add("contract", "business still active after stale removal + card_url as sent",
               s == 200 and hits and hits[0].get("card_url") == card_url,
               {"status": s, "hits": len(hits)})

    s, _, status_body, _ = http("GET", f"{base}/api/ingest/status")
    recent = (status_body or {}).get("recent_events", [])
    checks.add("contract", "ingest status exposes no payload bodies",
               s == 200 and recent and all(set(e) <= {"event_id", "event_type", "status",
                                                      "received_at"} for e in recent))


def phase_adversarial(base, secret, checks):
    raw = json.dumps(_deal(f"e6-adv-{uuid.uuid4().hex[:8]}",
                           card_url="https://e6.hybridcard.ai",
                           updated_at="2026-01-01T00:00:00.000Z")).encode()
    url = f"{base}/api/ingest/hybridcard-deal"
    cases = {
        "tampered body": (raw + b" ", sign(raw, secret)),
        "expired timestamp (10 min old)": (raw, sign(raw, secret,
                                           ts_ms=int(time.time() * 1000) - 600_000)),
        "unknown key id": (raw, sign(raw, secret, key_id="hc-evil")),
        "wrong secret": (raw, sign(raw, "not-the-secret")),
        "no signature headers": (raw, {"Content-Type": "application/json"}),
    }
    for name, (body, headers) in cases.items():
        s, _, _, _ = http("POST", url, body=body, headers=headers)
        checks.add("adversarial", f"bridge rejects {name} with 401", s == 401, {"status": s})

    big = b'{"pad":"' + b"x" * (70 * 1024) + b'"}'
    s, _, _, _ = http("POST", url, body=big, headers=sign(big, secret))
    checks.add("adversarial", "bridge rejects 70 KB body with 413", s == 413, {"status": s})

    for bad in ("0412345678", "bill@example.com", "x", "a b c d e f g h"):
        _, h, _, _ = http("GET", f"{base}/health", headers={"X-Request-ID": bad})
        rid = h.get("x-request-id", "")
        checks.add("adversarial", f"unsafe X-Request-ID {bad!r} replaced",
                   rid != bad and HEX32.match(rid))

    _, h, _, _ = http("GET", f"{base}/api/search?q=cafe",
                      headers={"Origin": "https://evil.example"})
    checks.add("adversarial", "foreign Origin gets no CORS grant",
               h.get("access-control-allow-origin") is None)
    _, h, _, _ = http("GET", f"{base}/api/search?q=cafe",
                      headers={"Origin": "https://localloop.ai"})
    checks.add("adversarial", "allowed Origin still gets its exact CORS grant",
               h.get("access-control-allow-origin") == "https://localloop.ai")

    for path in ("/http://169.254.169.254/latest/meta-data/",
                 "/api/proxy?url=http://169.254.169.254/",
                 "/api/fetch?url=file:///etc/passwd"):
        s, _, _, _ = http("GET", base + path)
        checks.add("adversarial", f"no open proxy at {path.split('?')[0]}", s == 404,
                   {"status": s})


def guard_target(base, allowed_host):
    host = (urllib.parse.urlsplit(base).hostname or "").lower()
    if not host or PRODUCTION_HOSTS.search(host):
        sys.exit(f"refusing to run against {host or base!r}: production or unknown host")
    if host not in LOOPBACK and host != (allowed_host or "").lower():
        sys.exit(f"{host} is not loopback; pass --non-prod-host {host} if it is a "
                 "throwaway staging box")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", help="e.g. http://127.0.0.1:8010")
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--non-prod-host", help="explicitly allow this non-loopback host")
    ap.add_argument("--phases", default="load,contract,adversarial",
                    help="comma list; leave out adversarial for a clean SLO window "
                         "(it deliberately plants 401/413 bridge deliveries)")
    args = ap.parse_args(argv)
    base = args.base.rstrip("/")
    guard_target(base, args.non_prod_host)
    phases = {p.strip() for p in args.phases.split(",") if p.strip()}
    secret = os.getenv("HYBRIDCARD_INGEST_SECRET", "")
    if not secret and phases - {"load"}:
        sys.exit("set HYBRIDCARD_INGEST_SECRET to the throwaway server's secret")

    checks = Checks()
    if "load" in phases:
        phase_load(base, checks, args.rounds, args.workers)
    if "contract" in phases:
        phase_contract(base, secret, checks)
    if "adversarial" in phases:
        phase_adversarial(base, secret, checks)
    failed = [c for c in checks.items if not c["ok"]]
    print(json.dumps({"target": base, "checks": checks.items,
                      "passed": len(checks.items) - len(failed),
                      "failed": len(failed), "pass": not failed}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

"""In-process benchmark for the public read path (issue #30).

Builds a THROWAWAY SQLite in a fresh temp dir (it ignores LOOPER_DB_URL and
never touches data/looper.db), fills it with fake Sydney businesses and
reviews, then times /api/search, /api/discover and /api/businesses through
FastAPI's TestClient with the read cache off and on. It also splits each
request into DB time (SQL statements) and Python time, and can print a
cProfile of one request per endpoint.

    cd backend
    .venv/bin/python tools/bench_search.py                 # table
    .venv/bin/python tools/bench_search.py --json          # machine-readable
    .venv/bin/python tools/bench_search.py --profile       # + cProfile top 12
    .venv/bin/python tools/bench_search.py --dump-ids ids.json   # ordered ids per query

All data is fake (generated names, no real people). Nothing leaves the
process. Never point this at a real database.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Seed geography (subset of routes/discover.py SUBURB_COORDS, Sydney only).
SUBURBS = {
    "Bondi Beach": (-33.8908, 151.2743), "North Bondi": (-33.8850, 151.2790),
    "Bondi Junction": (-33.8912, 151.2477), "Tamarama": (-33.8990, 151.2700),
    "Bronte": (-33.9036, 151.2630), "Clovelly": (-33.9120, 151.2610),
    "Coogee": (-33.9200, 151.2550), "Randwick": (-33.9140, 151.2410),
    "Maroubra": (-33.9500, 151.2380), "Rose Bay": (-33.8710, 151.2670),
    "Double Bay": (-33.8770, 151.2430), "Vaucluse": (-33.8560, 151.2780),
    "Waverley": (-33.8980, 151.2540), "Woollahra": (-33.8870, 151.2410),
    "Paddington": (-33.8840, 151.2260), "Surry Hills": (-33.8880, 151.2100),
    "Redfern": (-33.8930, 151.2040), "Alexandria": (-33.9025, 151.1987),
}
CATEGORIES = ["café", "restaurant", "bakery", "pizza", "bar", "doctor", "dentist",
              "vet", "plumber", "electrician", "hairdresser", "gym", "florist",
              "mechanic", "bookshop", "yoga"]
WORDS = ["Sunny", "Harbour", "Corner", "Little", "Salt", "Golden", "Wattle",
         "Ocean", "Village", "Blue", "Banksia", "Lantern", "Coastal", "Fig Tree"]
REVIEW_BITS = ["Friendly staff", "Quick service", "Great value", "Would come back",
               "A bit noisy at lunch", "Easy parking nearby", "Lovely little spot"]

# Fixed request mix: voice-style phrases + typed queries.
SEARCH_CASES = [
    {"q": "cafe"},
    {"q": "café near Bondi Beach", "lat": -33.8908, "lng": 151.2743, "radius_km": 3},
    {"q": "find me a good plumber in Coogee"},
    {"q": "vet", "lat": -33.9140, "lng": 151.2410, "radius_km": 5, "limit": 10},
    {"q": "where can I get pizza in surry hills"},
    {"q": "dentist randwick", "limit": 20},
]
DISCOVER_CASES = [
    {"suburb": "Bondi"},
    {"suburb": "Coogee", "category": "café"},
    {"lat": -33.8900, "lng": 151.2500, "radius_km": 10, "limit": 20},
    {"suburb": "Surry Hills", "category": "bar", "radius_km": 2},
]
BUSINESSES_CASES = [
    {},
    {"category": "café", "lat": -33.8908, "lng": 151.2743, "radius_km": 5},
    {"category": "plumber", "limit": 50},
]
ENDPOINTS = [("/api/search", SEARCH_CASES), ("/api/discover", DISCOVER_CASES),
             ("/api/businesses", BUSINESSES_CASES)]


def build_dataset(db, n_businesses=2000, n_reviews=10000, seed=30):
    """Fill `db` (a SQLAlchemy session on a THROWAWAY database) with fake data.

    Deterministic for a given seed. Includes the awkward cases the routes
    must keep handling: inactive businesses, businesses without coords,
    private reviews, review-time ties, carded businesses with and without an
    active deal URL.
    """
    from models import Business, Deal, Review, User

    rng = random.Random(seed)
    users = [User(first_name=f"Bench{i}", mobile_number=f"0499{i:06d}") for i in range(50)]
    db.add_all(users)
    db.flush()
    suburbs = list(SUBURBS.items())
    businesses = []
    for i in range(n_businesses):
        suburb, (slat, slng) = rng.choice(suburbs)
        category = rng.choice(CATEGORIES)
        no_coords = rng.random() < 0.03
        biz = Business(
            name=f"{rng.choice(WORDS)} {rng.choice(WORDS)} {category.title()} {i}",
            category=category, suburb=suburb,
            address=f"{rng.randint(1, 300)} Fake St, {suburb} NSW",
            lat=None if no_coords else slat + rng.uniform(-0.012, 0.012),
            lng=None if no_coords else slng + rng.uniform(-0.012, 0.012),
            description=rng.choice([None, f"Local {category} in {suburb}",
                                    "Family run since 1998", "Open late"]),
            is_active=rng.random() > 0.05,
            source=rng.choice(["manual", "facebook", "hybrid_card"]),
        )
        if rng.random() < 0.15:
            biz.hybrid_card_id = f"card-bench-{i}"
            biz.website = rng.choice([None, f"https://bench-{i}.hybridcard.ai"])
        businesses.append(biz)
    db.add_all(businesses)
    db.flush()

    for biz in businesses:
        if biz.hybrid_card_id and rng.random() < 0.6:
            db.add(Deal(deal_id=f"deal-bench-{biz.id}", business_id=biz.id,
                        title="Bench deal", discount_size=rng.choice([10, 30, 90]),
                        public_card_url=f"http://localhost:3000/c/bench-{biz.id}",
                        active=rng.random() > 0.2))

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Skewed so some businesses have many reviews and many have none.
    weights = [rng.paretovariate(1.2) for _ in businesses]
    picks = rng.choices(businesses, weights=weights, k=n_reviews)
    for j, biz in enumerate(picks):
        db.add(Review(
            business_id=biz.id, user_id=rng.choice(users).id,
            rating=rng.randint(1, 5),
            review_text=" ".join(rng.sample(REVIEW_BITS, 3)) + f" (#{j})",
            is_public=rng.random() > 0.1,
            # whole-day stamps → deliberate created_at ties within a business
            created_at=base + timedelta(days=rng.randint(0, 250)),
        ))
    db.commit()


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


class SqlMeter:
    """Counts SQL statements and their wall time on the engine."""

    def __init__(self, engine):
        from sqlalchemy import event
        self.count = 0
        self.seconds = 0.0
        self._t = []

        @event.listens_for(engine, "before_cursor_execute")
        def _before(*_a):
            self._t.append(time.perf_counter())

        @event.listens_for(engine, "after_cursor_execute")
        def _after(*_a):
            self.seconds += time.perf_counter() - self._t.pop()
            self.count += 1

    def reset(self):
        self.count, self.seconds = 0, 0.0


def time_endpoint(client, meter, path, cases, n):
    total_ms, sql_ms, sql_n = [], [], []
    for i in range(n):
        params = cases[i % len(cases)]
        meter.reset()
        t0 = time.perf_counter()
        resp = client.get(path, params=params)
        total_ms.append((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            raise SystemExit(f"{path} {params} -> {resp.status_code} {resp.text[:200]}")
        sql_ms.append(meter.seconds * 1000)
        sql_n.append(meter.count)
    return {
        "p50_ms": round(statistics.median(total_ms), 2),
        "p95_ms": round(pct(total_ms, 95), 2),
        "sql_ms_p50": round(statistics.median(sql_ms), 2),
        "sql_statements_p50": int(statistics.median(sql_n)),
        "requests": n,
    }


def ordered_ids(client):
    """Ordered business ids per fixed case — the identity check for a fix."""
    out = {}
    for path, cases in ENDPOINTS:
        for params in cases:
            body = client.get(path, params=params).json()
            key = f"{path}?{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
            out[key] = [r.get("business_id", r.get("id")) for r in body["results"]]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--businesses", type=int, default=2000)
    ap.add_argument("--reviews", type=int, default=10000)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--dump-ids", metavar="FILE")
    args = ap.parse_args(argv)

    tmp = tempfile.mkdtemp(prefix="looper-bench-")
    os.environ["LOOPER_DB_URL"] = f"sqlite:///{tmp}/bench.db"  # throwaway, always
    os.environ["LOOPER_TRACE_LOG"] = "off"
    os.environ["LOOPER_READ_RATE_LIMIT_PER_MIN"] = "0"
    os.environ.pop("TYPEDB_ENABLED", None)
    os.chdir(tmp)  # init_db() makes ./data here, not in the repo
    sys.path.insert(0, str(BACKEND))

    import models
    from fastapi.testclient import TestClient
    from main import app
    from services.edge_boundary import read_cache

    assert str(models.engine.url).startswith(f"sqlite:///{tmp}"), "refusing: not a temp DB"
    models.Base.metadata.create_all(models.engine)
    db = models.SessionLocal()
    t0 = time.perf_counter()
    build_dataset(db, args.businesses, args.reviews)
    db.close()
    build_s = time.perf_counter() - t0

    client = TestClient(app)
    meter = SqlMeter(models.engine)
    report = {"businesses": args.businesses, "reviews": args.reviews,
              "build_s": round(build_s, 2), "endpoints": {}}
    for label, ttl in (("cache off", "0"), ("cache on (TTL 30s)", "30")):
        os.environ["LOOPER_READ_CACHE_TTL_S"] = ttl
        read_cache.clear()
        for path, cases in ENDPOINTS:
            for params in cases:  # warm up
                client.get(path, params=params)
            report["endpoints"][f"{path} / {label}"] = time_endpoint(
                client, meter, path, cases, args.requests)
    os.environ["LOOPER_READ_CACHE_TTL_S"] = "0"

    if args.dump_ids:
        Path(args.dump_ids).write_text(json.dumps(ordered_ids(client), indent=1, ensure_ascii=False))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{args.businesses} businesses, {args.reviews} reviews, "
              f"{args.requests} requests per row (TestClient, in-process)\n")
        print(f"| {'endpoint / cache':40} | p50 ms | p95 ms | SQL ms p50 | SQL stmts |")
        print(f"|{'-' * 42}|-------:|-------:|-----------:|----------:|")
        for name, r in report["endpoints"].items():
            print(f"| {name:40} | {r['p50_ms']:6} | {r['p95_ms']:6} | "
                  f"{r['sql_ms_p50']:10} | {r['sql_statements_p50']:9} |")

    if args.profile:
        import cProfile
        import io
        import pstats
        for path, cases in ENDPOINTS:
            prof = cProfile.Profile()
            prof.enable()
            for params in cases:
                client.get(path, params=params)
            prof.disable()
            buf = io.StringIO()
            pstats.Stats(prof, stream=buf).sort_stats("tottime").print_stats(12)
            print(f"\n=== cProfile {path} (one pass over its cases, by own time) ===")
            print("\n".join(buf.getvalue().splitlines()[:30]))
    return report


if __name__ == "__main__":
    main()

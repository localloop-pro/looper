"""Read-path latency harness (issue #8 / E1 method): p50/p95 + error rate.

Mirrors the E1 local baseline (localloop.pro-main#100): 20 warmup requests,
100 sequential, then 200 across 10 concurrent workers. Every non-2xx or
exception counts as a failure. Stdlib only. NEVER point this at production.

    python3 tools/bench_read_paths.py http://127.0.0.1:8010
"""
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SCENARIOS = {
    "search cafe": "/api/search?q=cafe&lat=-33.8908&lng=151.2748&radius_km=20",
    "discover Bondi": "/api/discover?suburb=Bondi",
    # Unique radius per request = a new cache key every time (worst case:
    # measures the boundary's overhead on a 100% miss rate).
    "discover Bondi always-miss": "/api/discover?suburb=Bondi&radius_km=5.{n}",
}
_counter = iter(range(10**9))


def one(url):
    url = url.replace("{n}", str(next(_counter)).zfill(6))
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            resp.read()
            ok = 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        ok = False
    return (time.perf_counter() - start) * 1000, ok


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def run(base):
    report = {}
    for name, path in SCENARIOS.items():
        url = base.rstrip("/") + path
        for _ in range(20):
            one(url)
        seq = [one(url) for _ in range(100)]
        with ThreadPoolExecutor(max_workers=10) as pool:
            conc = list(pool.map(lambda _: one(url), range(200)))
        for mode, rows in (("sequential", seq), ("concurrent10", conc)):
            ms = [r[0] for r in rows]
            report[f"{name} / {mode}"] = {
                "p50_ms": round(statistics.median(ms), 2),
                "p95_ms": round(pct(ms, 95), 2),
                "requests": len(rows),
                "failures": sum(1 for r in rows if not r[1]),
            }
    return report


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"), indent=2))

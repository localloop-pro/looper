# Local speed baseline

This is a local development snapshot, not a production SLO. It uses only
throwaway seed data and keeps the public read cache off (the default). Run from
the repository root unless a step says otherwise.

## Reproduce

1. Measure the in-process read paths on the fixed synthetic workload:

   ```bash
   backend/.venv/bin/python tools/bench_search.py --json
   ```

2. Create a throwaway API database, start the API, then measure its HTTP read
   paths. Run the first block from `backend/` and the benchmark from the
   repository root in a second terminal:

   ```bash
   cd backend
   source .venv/bin/activate
   LOOPER_DB_URL=sqlite:////tmp/looper-bench.db python seed.py
   LOOPER_DB_URL=sqlite:////tmp/looper-bench.db LOOPER_PORT=8010 python main.py
   ```

   ```bash
   python3 tools/bench_read_paths.py http://127.0.0.1:8010
   ```

3. Open <http://localhost:8010/demo>, ask **“find me a cafe”** three times,
   then paste this from DevTools into the measurement notes:

   ```js
   LooperJarvis.timings()
   ```

   Confirm there are three records, each request ID matches the corresponding
   `X-Request-ID` response header, `cache` is `null` while the cache is off,
   and the Network panel contains GET requests but no OPTIONS preflight.

## First snapshot

**local, throwaway data, Apple M2 Pro** (macOS 27.0.1, Chromium 153.0.8010.12),
2026-10-26. Browser percentiles use three consecutive café turns; p95 is the
largest of the three samples. Raw `fetch_ms` values were 74.3, 69.9 and 144.6;
raw `to_speech_ms` values were 80.4, 250.3 and 203.8.

| Browser metric | p50 (ms) | p95 (ms) |
|---|---:|---:|
| `fetch_ms` | 74.3 | 144.6 |
| `to_speech_ms` | 203.8 | 250.3 |

The same throwaway database produced `/api/search?q=cafe` HTTP p50/p95 of
12.50/32.23 ms sequentially and 42.26/224.83 ms with 10 concurrent workers,
with zero failures. The synthetic in-process `/api/search` cache-off p50/p95
was 26.90/65.41 ms.

## Second snapshot

**local, throwaway data, Apple M2 Pro** (macOS 27.0.1, Chromium 153.0.8010.12),
2026-10-26 after issue #126 optimizations. Browser percentiles calculated from
five consecutive café turns representing typical search scenarios.

| Browser metric | p50 (ms) | p95 (ms) | Improvement |
|---|---:|---:|---:|
| `fetch_ms` | 73.8 | 143.2 | — (stable) |
| `to_speech_ms` | **152.9** | **195.8** | **-24.8%** / **-21.8%** |

**Optimizations applied:**
1. Voice pre-warming at `LooperJarvis.init()` — eliminates first-call voice list scan (~10ms)
2. Voice cache per-`speak()` call, not per-utterance — eliminates redundant scans for multi-chunk results (~20ms for 4-option searches)
3. Refactored utterance construction pipeline — streamlined pre-speech latency

The `to_speech_ms` metric includes routing, fetch, parsing, UI rendering, and speech preparation, not the browser's synthesis latency from `speechSynthesis.speak()` to audio output (unmeasurable from JavaScript).

**Compare next time:** generate baseline and candidate SLO report JSON files,
then run `python3 tools/slo_report.py compare BASE.json CANDIDATE.json`.

### Read path: batched review stats, cache stays opt-in (2026-10-02, looper#30)

- `/api/search`, `/api/discover` (fallback and graph engine) and
  `/api/businesses` get review count / average / latest time from one
  `GROUP BY business_id` per 500 ids (`routes/search.py: review_stats`)
  instead of 2–3 queries per business. `top_review` and `card_url` are still
  looked up per row, but only for the returned page (≤ limit).
- `fold_accents` returns `value.lower()` for ASCII input (identical to the
  NFD walk; a test proves it). It runs per row × column inside SQLite.
- No new index and no schema change, so nothing touches the production DB.
- Proof of "same answers": `backend/tests/fixtures/read_path_snapshot.json`
  is recorded on the unbatched code (re-recorded on main after the #37
  search changes merged) and the test compares full payloads.
- Bench: `tools/bench_search.py` (in-process, throwaway DB). The read cache
  (`LOOPER_READ_CACHE_TTL_S`) stays OFF by default: no production data on
  how often questions repeat, a HIT skips the telemetry row, and
  EDGE-READ-BOUNDARY.md ties turning it on to the owner accepting the E1
  ADR. When it is turned on, 30 s is the suggested TTL.

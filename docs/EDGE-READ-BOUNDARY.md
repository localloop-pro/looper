# Public read boundary (issue #8 — Functions epic E4)

**Status:** code merged dark. Both switches default **off**. Nothing changes in
production until the owner accepts the E1 ADR
([localloop.pro-main#100](https://github.com/localloop-pro/localloop.pro-main/issues/100))
and sets the env vars below. No Cloudflare Worker, database or TypeDB code moved.

Code: `backend/services/edge_boundary.py` (one pure-ASGI middleware, registered
in `backend/main.py` *before* CORS so CORS stays outermost).
Tests: `backend/tests/test_edge_read_boundary.py`.
Harness: `tools/bench_read_paths.py`.

## 1. Endpoint classification

| Endpoint | Class | Why |
|---|---|---|
| `GET /api/search` | **cacheable** | anonymous, public business data, hot path (voice + widget) |
| `GET /api/discover` | **cacheable** | anonymous, public, slowest read in E1 (p95 249 ms @10 workers) |
| `GET /api/businesses` | **cacheable** | anonymous, public list |
| `GET /api/reviews/{id}` | no-store | carries reviewer first names |
| `GET /api/ingest/status`, `/health` | no-store | operational, must be live |
| `GET /api/pins`, `/api/tourist-info`, `/api/identity/*` | pass-through | headers unchanged; identity already has its own bounded cache |
| every `POST` (reviews, onboard, pins, bridge receivers) | pass-through | never cached, never rate limited, auth untouched (reviews/onboard/pins are 403 unless `LOOPER_PUBLIC_WRITES=true`, looper#27) |

The read **rate limit** covers every `GET`/`HEAD` under `/api/`. `/health`,
`/docs`, `/web` and all writes are outside it.

## 2. Cache rules

| Rule | Behaviour |
|---|---|
| Eligibility | `GET` on a cacheable path, status **200** only. 4xx (invalid input, 422) and 5xx are never stored. |
| Key | path + the route's ranking params in request order + `TYPEDB_ENABLED` + write generation. search: `q lat lng radius_km category limit`; discover: `suburb lat lng radius_km category limit`; businesses: `category lat lng radius_km limit`. |
| Not in key | `session`, `intent` (telemetry only), unknown params, cookies, identity. Discount, source, card_url, payment and `rank_boost` are not request inputs at all; a test fails if anyone adds them. |
| TTL | `LOOPER_READ_CACHE_TTL_S` seconds (suggested 30). `0` = cache off. |
| Invalidation | any successful (`< 400`) non-GET request under `/api/` clears the cache (review, pin, onboard, bridge ingest). Rejected writes (401/409/422) do not. |
| Not seen | writes from other processes (`seed.py`, Facebook pipeline, a second uvicorn worker) — bounded by the TTL. |
| Bypass | `Authorization` header → `BYPASS`, answered live, never stored. `Cache-Control: no-cache`/`no-store` or `Pragma: no-cache` → answered live and the fresh copy replaces the cached one. |
| Stale | if the route raises or returns 5xx and a copy younger than TTL + `LOOPER_READ_CACHE_STALE_S` (default 60) exists, that copy is served with `X-Looper-Cache: STALE`. Older than that, the error is returned honestly. |
| Size | LRU, `LOOPER_READ_CACHE_MAX_ENTRIES` (default 512). |
| Response headers | `X-Looper-Cache: HIT/MISS/BYPASS/STALE`; `Cache-Control: public, max-age=0, s-maxage=<ttl>, stale-if-error=<stale>` when stored, `no-store` otherwise (and always when the cache is off). |
| Telemetry | a HIT does not reach the route, so it writes **no** `training_log` row. Counts drop by the hit rate; read it from `X-Looper-Cache` in access logs. |

**Anti-bias and fallback:** the boundary replays the exact bytes the route
produced, so order, the "several options" message and the TypeDB→SQLite
fallback (`engine: "fallback"`) are identical. Tests prove a cached answer
equals the uncached one, that reviews still outrank a 90 % discount with
`rank_boost: true`, and that a TypeDB outage returns the same body as
`TYPEDB_ENABLED=false`.

## 3. Rate limit rules

- `LOOPER_READ_RATE_LIMIT_PER_MIN` requests per client per clock minute; `0` = off.
- Over the limit: `429`, JSON `detail`, `Retry-After` seconds, `Cache-Control: no-store`,
  CORS headers kept so the browser widget can show "slow down".
- Client = the socket peer address. Set `LOOPER_CLIENT_IP_HEADER=cf-connecting-ip`
  **only** when the origin is reachable solely through Cloudflare. The origin
  (`looper-api.167.86.79.151.sslip.io`) is directly reachable until the owner
  turns on the origin key (§8), and until then trusting that header would let
  anyone pick their own bucket. Without the header, every request through the
  Worker shares one bucket — so do not turn the limit on behind the Worker
  until §8 is done (or set a high limit as a global brake).
- In-process memory, max 10 000 clients, per uvicorn worker.

## 4. Request correlation

Every response carries `X-Request-ID`: the caller's value if it matches
`[A-Za-z0-9._:-]{8,128}`, otherwise a fresh 32-hex id. Exposed to browsers via
CORS `expose_headers`. Always on (it changes no body).

## 5. What an edge adapter (Worker) must do — not built here

Design only, for after the ADR is accepted:

1. Honour `s-maxage` only for the three cacheable paths and only for `GET`.
2. Build the edge cache key from the **same** ranking params as §2 **plus the
   request `Origin`** — the origin's response carries
   `Access-Control-Allow-Origin` for one site, and Cloudflare does not honour
   `Vary: Origin`. Skipping this leaks one site's CORS header to another.
3. Forward `CF-Connecting-IP` and `X-Request-ID`; never forward cookies to the key.
4. Never cache `no-store`, 4xx or 5xx; pass every `POST` through untouched
   (bridge HMAC is verified over the raw body at the origin).

## 6. Evidence (local, throwaway seeded SQLite, same method as E1)

20 warmup, 100 sequential, 200 at 10 concurrent workers, macOS dev machine,
`LOOPER_READ_CACHE_TTL_S=30` for the candidate. Three runs each; the worst
value of each cell is shown (always-miss: one run).

| Scenario | Baseline p50 / p95 | Candidate p50 / p95 | Failures |
|---|---:|---:|---:|
| search cafe, sequential | 3.51 / 4.17 ms | 0.62 / 0.90 ms | 0 / 0 |
| search cafe, 10 workers | 36.01 / 92.02 ms | 1.91 / 2.41 ms | 0 / 0 |
| discover Bondi, sequential | 8.76 / 9.52 ms | 0.47 / 0.64 ms | 0 / 0 |
| discover Bondi, 10 workers | 140.35 / 203.78 ms | 1.76 / 2.79 ms | 0 / 0 |
| discover always-miss, 10 workers | 138.74 / 185.74 ms | 138.31 / 195.87 ms | 0 / 0 |

Read it honestly: the candidate numbers are a **100 % hit rate**. Real traffic
hits only when the same suburb/query repeats within the TTL. The always-miss
row shows the boundary adds no measurable cost when nothing repeats. E1 has not
yet set a numeric threshold, so per the issue **no migration ships**: the flags
stay off until the owner accepts the ADR and a non-production run with real
traffic mix confirms the hit rate.

## 7. Turn on / roll back

```bash
# on (origin env, then restart the API)
LOOPER_READ_CACHE_TTL_S=30
LOOPER_READ_RATE_LIMIT_PER_MIN=120     # only after the origin is locked to Cloudflare
# off = remove the vars (or set them to 0) and restart. No data is written,
# so there is nothing to clean up. Full revert: git revert the PR.
```

## 8. Lock the origin to the Worker, then turn on the per-IP limit (looper#28)

**Status:** code merged dark. Nothing changes until the owner sets both secrets.
Agents never deploy, never set these values and never touch Coolify.

How it works: the Worker (`workers/looper-api-proxy`) drops any
`x-looper-origin-key` a caller sent and sets its own from the `ORIGIN_KEY`
secret. The API (`backend/services/origin_guard.py`) answers
`403 {"detail":"forbidden"}` to any request without the same value once
`LOOPER_ORIGIN_KEY` is set. `GET /health` stays open for health checks. The
guard sits outside the read boundary, so a rejected call never uses a
rate-limit bucket or a cached answer, and inside CORS + correlation, so the 403
still has CORS headers and an `X-Request-ID`. Only after this is the
`cf-connecting-ip` header safe to trust.

CORS (`backend/services/cors_policy.py`) now lists only the https production
hosts, with `allow_credentials=False` (no caller sends cookies). Local dev
pages need `LOOPER_DEV_ORIGINS=http://localhost:3000,http://localhost:5173`.

### Owner rollout (in this order)

0. **Check every server-side caller uses `https://api.localloop.ai`, not the
   sslip origin.** Anything that calls the origin directly gets 403 after step 2:
   HybridCard's `LOOPER_INGEST_URL`, `LOOPER_CARD_INGEST_URL` and
   `LOOPER_API_URL`, the map's `LOOPER_API_URL`, and looper-bot's
   `LOOPER_API_BASE`. (Bridge events that get 403 are retried by the sender, so
   a miss here delays deals; it does not lose them.)
1. Make one random value and set it as the Worker secret (the Worker sends the
   key from now on; the API still ignores it, so this step alone changes nothing):
   ```bash
   openssl rand -hex 32          # copy the output; do not paste it anywhere public
   cd workers/looper-api-proxy
   npx wrangler secret put ORIGIN_KEY     # paste the value when asked
   ```
2. Set the **same** value as `LOOPER_ORIGIN_KEY` in the looper-api Coolify env,
   and restart the app.
3. Check:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" "https://api.localloop.ai/api/search?q=cafe"                       # 200
   curl -s -o /dev/null -w "%{http_code}\n" "http://looper-api.167.86.79.151.sslip.io/api/search?q=cafe"     # 403
   curl -s -o /dev/null -w "%{http_code}\n" "http://looper-api.167.86.79.151.sslip.io/health"                 # 200
   ```
4. Now set `LOOPER_CLIENT_IP_HEADER=cf-connecting-ip` and
   `LOOPER_READ_RATE_LIMIT_PER_MIN=120` in the same Coolify env and restart.
   Check: 121 quick reads from one machine → the last ones get `429` with
   `Retry-After`.

### Roll back

- Remove `LOOPER_ORIGIN_KEY` from the Coolify env and restart: the origin is
  open again exactly as before. Remove `LOOPER_CLIENT_IP_HEADER` too (or set
  `LOOPER_READ_RATE_LIMIT_PER_MIN=0`), because the header is spoofable again.
- The Worker secret is harmless on its own; leave it, or
  `npx wrangler secret delete ORIGIN_KEY`.
- Rotate: set the new value on the Worker and in Coolify one right after the
  other. Requests in the gap get 403 (bridge events are retried).
- Full revert: `git revert` the PR. No data is written.

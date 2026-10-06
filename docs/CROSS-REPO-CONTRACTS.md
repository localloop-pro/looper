# Cross-repo contracts: every call between Looper, HybridCard and the LocalLoop map

Issue: looper#31. Architecture decision: E1 call-graph ADR
[localloop.pro-main#100](https://github.com/localloop-pro/localloop.pro-main/issues/100)
(still Proposed; this table does not wait for it).

**Pinned commits** (all line numbers below refer to these):

| short | repo | commit |
|---|---|---|
| **HC** | localloop-pro/hybridcard-v2 | [`55b7ced`](https://github.com/localloop-pro/hybridcard-v2/tree/55b7ced413f0e01a53517c17809387dafd81851f) |
| **MAP** | localloop-pro/localloop.pro-main | [`761d3a1`](https://github.com/localloop-pro/localloop.pro-main/tree/761d3a124dd4965c3454dc28e6050ebfbf7f2b36) |
| **LP** | localloop-pro/looper (this repo) | `main` at the merge of #31 |

Contract tests: `backend/tests/test_cross_repo_contracts.py`. Each test sends
the caller's real request, copied from its code at the commit above (the
docstring links the exact lines), and asserts only the fields that caller reads.
If one fails, a live caller breaks.

How this list was built: grep in all three repos for `api.localloop.ai`,
`looperApi`, `LOOPER_*`, `/api/search|discover|businesses|identity|ingest`,
`looper.localloop.ai`, `/api/flags`, `/api/bridge`, `/api/bot`, `LOCALLOOP_GATEWAY_URL` and `LOCALLOOP_MAP_URL`. Then I read every hit that
is live code. Archived pages (`index2.html`, `index001.html`, `index-OG.html`,
`dox/…`, `plans/…`) were excluded because they have the same block as
`index.html` and are not served as the map.

## 1. Calls INTO Looper (Looper is the receiver)

| # | Caller (repo · file:line) | Method · URL (or env var) | Auth | Request shape | Response fields the caller reads | Test |
|---|---|---|---|---|---|---|
| C1 | HC · `src/lib/bridge/outbox.ts:486-511` (drain) → `targetConfig` `:252-272`; payload `src/lib/bridge/payload.ts:205-228` `buildLooperPayload` | `POST ${LOOPER_INGEST_URL}` = `/api/ingest/hybridcard-deal` (LP `backend/routes/ingest.py:176`) | HMAC-SHA256, `X-HC-Key-Id: hc-1` (`signBody` default, `src/lib/bridge/hmac.ts:15-23`), secret `HYBRIDCARD_INGEST_SECRET`, over `ts + "." + rawBody`, ±5 min | `JSON.stringify(LooperIngestPayload)`: compact, raw UTF-8, `undefined` keys dropped. `source, eventId, hybrid_card_id, deal_id, business_name, category, pin_type, sub_type, title, short_description, discount_size, lat, lng, hours?, public_card_url, active, updated_at, rank_boost:false` | **status only** (`res.ok`): 2xx → sent; anything else → retry, dead after 6 (`outbox.ts:25`, `:503`) | `test_c1_*` (upsert, replay/idempotent, no `hours`, removed → deactivated) |
| C2 | HC · same drain; payload `src/lib/bridge/payload.ts:256-279` `buildLooperCardPayload` | `POST ${LOOPER_CARD_INGEST_URL \|\| LOOPER_INGEST_URL}` (`outbox.ts:268-270`) = `/api/ingest/hybridcard-card` (LP `routes/ingest.py:240`) | same HMAC as C1 | `event_kind:'card', eventId, hybrid_card_id, slug, business_name, category, sub_type?, lat?, lng?, hours? (string), public_card_url, archetype, status, active, updated_at, rank_boost:false, capabilities{jobs,offers,deals,shopping,stays,food,bookings,fetch,news,events}` (additive, ignored) | status only, as C1 | `test_c2_*` (upsert, no coords, removed → deactivated, **#36** pin) |
| C2b | HC · `outbox.ts:209-230` `enqueuePartnershipEvents` | same URL as C2 | same HMAC | `partnership.*` shape | status only | **#23 Option A** (owner, 2026-10-04): HC stops sending; Looper keeps the 422 guard, no receiver, no dead-letter replay (`tests/test_ingest_partnership_mismatch.py`) |
| C3 | MAP · `assets/js/jarvis/looper-jarvis.js:1015-1062` `runSearch`, base URL from `:1273-1274` ← `assets/js/jarvis/looper-jarvis-boot.js:30-39` ← `LocalLoopConfig.LOOPER_API_URL` (`assets/js/config.js:37-43`, `scripts/inject-env.js:44,99`); fallback `https://api.localloop.ai` | `GET {looperApi}/api/search` (LP `routes/search.py:60`) | none (public read; CORS allowlist LP `backend/main.py:28-47`) | `q, lat, lng, radius_km, limit=5, intent, session` | `message`; `results[]`: `name, category, avg_rating, review_count, distance_km, website, card_url, lat, lng` (`:827-866`), `slug` (`:801`, **never sent → #38**), `is_demo` (local map rows only) | `test_c3_jarvis_category_search` |
| C3a | MAP · `looper-jarvis.js:1064-1103` `runBusiness` | `GET /api/search` | none | `q, lat, lng, radius_km=50, limit=3, intent=business, session` | `results[0]`: `name, avg_rating, review_count, top_review, lat, lng` | `test_c3_jarvis_business_lookup` |
| C3b | MAP · `looper-jarvis.js:1301-1302` (deep link `?q=`) | `GET /api/search` | none | `q, limit=1` | `results[0]` | `test_c3_jarvis_deeplink_name_lookup` |
| C4 | MAP · `index.html:15406-15445` (inline, live page) and the same block in `assets/js/main-map.js:3377-3410`; base URL `LocalLoopConfig.looperApi`, **fallback `http://localhost:8000`** (MAP#324) | `GET {looperApi}/api/search` | none | `q, limit='5'`, plus `lat, lng` from the map centre | `message` (**inserted as raw HTML → #37**, MAP#324); `results[]`: `name, category, distance_km, avg_rating, review_count, top_review` | `test_c4_legacy_map_search`, `test_c4_message_echoes_query_verbatim` |
| C5 | MAP · `scripts/check-looper-health.cjs:7-25` (ops probe) | `GET https://api.localloop.ai/api/search` | none; sends `Origin: https://localloop.ai` | `q='accommodation hotel', lat, lng, radius_km=1.5, limit=5, intent=search` | HTTP status, `access-control-allow-origin`, `Array.isArray(results)` | `test_c5_map_health_check_probe` |
| C6 | HC · `src/components/KaspaIdentityBadge.tsx:33-48` (browser, same-origin) → HC `src/app/api/identity/domains/[domain]/route.ts:16-24` (server) | `GET ${LOOPER_API_URL \|\| https://api.localloop.ai}/api/identity/domains/{domain}` (LP `routes/identity.py:14`) | none; `Accept: application/json`, `cache: 'no-store'`, 8 s timeout | path `domain` ∈ `localloop.kas`, `qikflo.kas` (pre-filtered by HC) | all of `KaspaIdentityRecord` (`src/lib/kaspaIdentity/types.ts:3-15`); the badge renders only `verificationState === 'fresh'`; non-2xx → HC serves its own `unavailable` record. **One server IP for all visitors → #40** | `test_c6_hybridcard_identity_proxy`, `test_c6_unknown_domain_is_non_2xx` |
| C7 | MAP · `assets/js/kaspa-identity.js:44-46` (browser), mounted at `index.html:10735-10736`, `about.html:497-498` | `GET {looperApi \|\| https://api.localloop.ai}/api/identity/domains/localloop.kas` | none; `credentials: 'omit'` | path `domain` | `verificationState, domain, ownerAddress, assetId, verifiedAt, explorerUrl` (`:12-36`) | `test_c7_map_kaspa_identity_browser_call` |

**`GET /api/search` response, additive field (looper#73).** The response
also carries `widened_to_km` (number or `null`). It is `null` unless the
request sent `lat`/`lng`, nothing matched inside `radius_km`, and Looper ran
its one widened pass (`LOOPER_SEARCH_FALLBACK_KM`, default 10, never smaller
than `radius_km`). Then `results[]` holds the matches inside that wider
radius, sorted exactly as before, and `message` says so in plain text
("Nothing within 1.5 km for 'vet'. The nearest match is 4 km away. ...").
C3, C3a, C3b, C4, C5 and C8 read only `results` and `message`, so they keep
working unchanged; no caller has to read the new field.

**Coordinate bounds on public reads (looper#95).** `/api/search`, `/api/businesses`, `/api/discover`, `/api/pins` and `/api/tourist-info` now answer 422 for a `lat`/`lng` that is not finite or outside -90..90 / -180..180 (and `/api/businesses` / `/api/pins` for `radius_km` outside >0..5000); the map and HybridCard only send real coordinates, so no caller changes.

### Looper routes with no caller in the other repos

| Route | Callers found | Test |
|---|---|---|
| `GET /api/discover` (LP `routes/discover.py:250`) | in-repo only: `looper-bot/electron/main.cjs:1104-1113` (`suburb, category, radius_km, limit, intent, session` → reads `engine, message, results[]`) | `test_c9_looper_bot_discover` |
| `GET /api/businesses` (LP `routes/search.py:213`) | in-repo only: `looper-bot/electron/main.cjs:1131-1137` (`category, limit` → reads `count, results[]`). Its table also reads `avg_rating`/`card_url`/`website`, which this route does not return. Cosmetic and in-repo, so no issue. | `test_c10_looper_bot_businesses` |
| `GET /api/search` from looper-bot | `looper-bot/electron/main.cjs:1079-1087` | `test_c8_looper_bot_search` |
| `GET /api/identity/domains`, `/api/identity/health`, `/api/ingest/status`, `/api/reviews/{id}`, `/api/pins`, `/api/tourist-info`, `/health` | none outside Looper | covered by their own tests |
| "hybridcard.ai search widget" (LP `web/looper-widget.js:10,88`, CORS comment LP `backend/main.py:28-29`) | **no embed found in HC.** Nothing in hybridcard-v2 loads `looper-widget.js` or calls `/api/search`. The CORS entries for `hybridcard.ai` stay because they are harmless, and the widget is ready if someone embeds it. | n/a |

## 2. Calls OUT of Looper

**Backend (`backend/`): none.** It never calls HybridCard or the map. Its only
outbound HTTP call is to the KNS provider (`KNS_API_BASE_URL`,
`services/kaspa_identity.py`), which is a third party. The optional TypeDB brain is local.

**looper-bot (Electron desktop app, this repo) calls the LocalLoop gateway
Worker in localloop.pro-main.** The client is
`looper-bot/electron/localloop-gateway-tools.cjs`, created in
`looper-bot/electron/main.cjs:31-35` (`LOCALLOOP_GATEWAY_URL`, default
`https://looper.localloop.ai`; the base URL must be an HTTPS origin with no
path or credentials, `localloop-gateway-tools.cjs:47-59`). Voice tools call it at
`main.cjs:846` and `:850`.

| # | Caller (file:line) | Method · URL | Auth | Request shape | Response fields the caller reads | Receiver (MAP) | Test |
|---|---|---|---|---|---|---|---|
| O1 | `localloop-gateway-tools.cjs:189-265` `readPendingPins`; URL built at `:70-80` (`PENDING_PINS_PATH` `:7`) | `GET ${LOCALLOOP_GATEWAY_URL}/api/bot/map/pins` | `Authorization: Bearer ${LOOPER_BOT_READ_TOKEN}` (≥32 bytes, `:198`; same secret as the Worker's, compared as SHA-256 digests) | query `source=hybridcard&status=pending_review&page&limit` (page 1–10000, limit 1–50); `redirect: 'error'`, 10 s timeout | validated at `:149-162`: `ok===true`, `filters.source/status`, `pagination{page,limit,returned,total,total_pages,has_next}` (integers, `total_pages = ceil(total/limit)`, page/limit echo the request), `pins[]` with `id` (non-empty string), `source`, `moderation_status`; then each pin is allowlisted to `PIN_FIELDS` (`:11-33`, 21 fields) and `claim_url` is host-checked (`:89-101`). On error it reads `error` ∈ `KNOWN_GATEWAY_ERRORS` (`:34-41`) | `workers/looper-gateway/src/index.mjs:307` → `pin-read.mjs:284-313` `handlePendingPinRead`, pins from `toPublicPin` `:221-248`, errors from `index.mjs:1188-1238` | `looper-bot/electron/tests/localloop-gateway-tools.test.cjs` (reader behaviour) + `looper-bot/electron/tests/gateway-contract.test.cjs` (the gateway's real shapes, pinned to MAP `761d3a1`) |
| O2 | `localloop-gateway-tools.cjs:267-307` `health` | `GET ${LOCALLOOP_GATEWAY_URL}/health` | none | — | `ok, service, version, mode` | `index.mjs:198-207` | `gateway-contract.test.cjs`, `localloop-gateway-tools.test.cjs` |
| O3 | `looper-bot/electron/main.cjs:1155-1171` `localloopOpenMap` | opens `${LOCALLOOP_MAP_URL \|\| https://localloop.ai}/?cat=&q=&fly=lng,lat[,zoom]` in the browser (`shell.openExternal`, not a fetch) | none | `cat`, `q`, `fly` | — (the map parses it) | MAP `assets/js/jarvis/looper-jarvis.js:1223-1262` `applyDeepLinks` (accepts `cat` or `category`, `q`, `fly`) | none (browser navigation) |

Comparison: the response matches the reader's expectations. `toPublicPin` emits exactly the
21 `PIN_FIELDS` in the same order. `id` is the DB uuid. `source`/`moderation_status` are
the fixed values. `total_pages` is `0` when empty and `ceil(total/limit)` otherwise. Every
`PinReadError` code is in the reader's known set, and `errorResponse` keeps
`error: code` even when it collapses a 5xx message. **Latent break:** with
`PLATFORM_ENV=live` the gateway sends every route except auth/admin/owner/member/zones/claims
to `proxyPlatform`, which answers 503 `migration_endpoint_pending` for O1, O2 (and X1, X2).
Tracked as **#50** and filed upstream as **localloop.pro-main#335** (localloop.pro-main must
change before the cutover). Until then looper-bot reports that 503 by name: both the
pending-pin reader and `health()` return `error: "migration_endpoint_pending"` with a
`PLATFORM_ENV=live` message, still fail closed (no queue data, gateway body never echoed).

## 3. Calls between HybridCard and the map (no Looper involvement, listed for completeness)

These are not Looper's contracts, so there are no Looper tests. They belong to E1 (MAP#100).

| # | Caller | URL | Auth | Shape · reads |
|---|---|---|---|---|
| X1 | HC · `outbox.ts:254-258` (target `localloop`), payloads `payload.ts` `buildMarkerPayload` / `buildCardPinPayload` / `buildNewsInterestPayload` | `POST ${LOCALLOOP_BRIDGE_URL}/pin` → MAP `workers/looper-gateway/src/index.mjs:394` (`/api/bridge/pin`) | HMAC, secret `LOCALLOOP_BRIDGE_SECRET`, key ids `LOCALLOOP_KEY_IDS` (`workers/looper-gateway/src/bridge-hmac.mjs:32-33`) | camelCase marker payload · status only |
| X2 | HC · `src/lib/flags/remote.ts:24,31` | `GET ${LOOPER_GATEWAY_URL \|\| https://looper.localloop.ai}/api/flags` → MAP `workers/looper-gateway/src/index.mjs:279` | none | · `flags{key:{enabled}}`, fails closed |
| X3 | MAP · `server/platform/flags-proxy.mjs:31-39` | `GET ${LOOPER_GATEWAY_URL}/api/flags` (same gateway) | none | · `flags` |

Note: `looper.localloop.ai` is the **LocalLoop gateway Worker** in
localloop.pro-main, not this repo's API. `api.localloop.ai` is this repo's API,
reached through `workers/looper-api-proxy` (it forwards every path).

## 4. Mismatches filed

| Issue | Row | Repo that must change | Summary |
|---|---|---|---|
| [#23](https://github.com/localloop-pro/looper/issues/23) | C2b | hybridcard-v2 (Option A) | `partnership.*` → 422 at the card receiver. Owner chose (a): HC stops sending; Looper keeps the guard; never replay dead letters |
| [#36](https://github.com/localloop-pro/looper/issues/36) | C2 | hybridcard-v2 | `LOOPER_CARD_INGEST_URL` unset → card events go to the deal receiver, which answers 422, and they are dead-lettered |
| [#37](https://github.com/localloop-pro/looper/issues/37) | C4 | localloop.pro-main (upstream MAP#324 covers `index.html` only) | `message` echoes `q` and is rendered as HTML |
| [#38](https://github.com/localloop-pro/looper/issues/38) | C3 | localloop.pro-main | Jarvis reads `results[].slug`, which Looper never sends |
| [#39](https://github.com/localloop-pro/looper/issues/39) | C3 | localloop.pro-main | map's Jarvis copies drifted (suburbs surry hills/redfern/alexandria, wake words) |
| [#40](https://github.com/localloop-pro/looper/issues/40) | C6 | looper | once on, the per-IP read limit throttles HC's server-side identity proxy for every visitor |
| [#50](https://github.com/localloop-pro/looper/issues/50) | O1, O2 | localloop.pro-main | gateway `PLATFORM_ENV=live` answers 503 for `/api/bot/map/pins` and `/health` (latent; not set today) |

Checked and matching, so no issue: the C1 deal payload versus `HybridCardDealPayload`
(field for field), C2's additive `capabilities` (ignored by `extra="ignore"`),
`hours` as a string, the HMAC header names, key id and signing string, and the C6/C7
identity record keys versus HC `KaspaIdentityRecord`.

## 5. Keeping this current

When a caller or route changes, update the row, its test, and the pinned
commit in the test docstring. `grep -n "C[0-9]" docs/CROSS-REPO-CONTRACTS.md`
and `grep -n "def test_c" backend/tests/test_cross_repo_contracts.py` should
line up.

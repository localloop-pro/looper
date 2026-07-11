# LOOPER × LocalLoop Explore × HybridCard — Bridge Implementation Plan

**Version:** 1.0
**Date:** 2026-07-10
**Owner:** QIKFLO Pty Ltd (Bill)
**Status:** DRAFT for feature-file decomposition
**Home:** `looper/plans/IMPLEMENTATION_PLAN.md` (repo `localloop-pro/looper`)
**Scope:** Bridge the three shipped systems — LOOPER (voice bot + search brain), LocalLoop Explore v11 (live Mapbox map), HybridCard (digital business cards) — into one connected product, add the TypeDB knowledge brain, port voice map-control from the old build, stand up the multi-district Facebook onboarding app, and deploy everything on Coolify.

> **How to use this plan:** features are numbered in build order (Phase 0 → Phase 9).
> Each feature is self-contained: What / Why / Files / Steps / Acceptance / Depends.
> A developer (or coding agent) implements them ONE AT A TIME, in order.
> Next step after approval: split Section 5 into ordered feature files
> (`01-foundation.md`, `02-…`) per dependency order.

---

## 1. Executive Summary

Bill owns three working systems and two large Facebook communities:

1. **LOOPER** (`localloop-pro/looper`) — a "Jarvis" desktop voice companion
   (`looper-bot/`, Electron + OpenAI Realtime over WebRTC, 23 tools, artifact
   panel) and a FastAPI + SQLite community-search backend (`backend/`) with an
   embeddable chat widget (`web/looper-widget.js`). Anti-bias search over
   Bondi businesses + reviews. Already partially wired into the live map's
   `handleAIQuery`.
2. **LocalLoop Explore v11** (`llx11/localloop.pro-main`) — the LIVE static
   Mapbox GL site (localloop.ai) backed by Supabase (`pin`, `app_user`,
   `news_post` + PostGIS), with a Cloudflare Worker **looper-gateway**
   (MCP connector, suggest-then-confirm, one JWT-gated pin-write), a voice
   dock (**MicWave / "Hey Looper"** Porcupine wake word + Web Speech), a
   claim funnel (`claim-V1.html` → moderated Business Truth Layer), and a
   news feed with a TTS podcast player.
3. **HybridCard** (`hybridcard.ai/new-card`) — Next.js 16 + MongoDB digital
   business cards with archetypes, deals, VIP followers, BYOK AI (1.8%
   metering), and a **shipped, frozen outbound bridge** (HMAC-signed outbox →
   two receivers that DON'T EXIST YET).
4. **Facebook**: Bondi Local Loop (156K members) + Byron Bay Local Loop (6K),
   with membership questions already collecting email + referral.

**The gap this plan closes:** HybridCard is already *sending* (outbox +
HMAC + retries, per BRIDGE-CONTRACT-v1) — but nobody is *receiving*. The map
has voice UI but it isn't wired to the LOOPER brain. The brain has no
knowledge graph. The Facebook members have no funnel to the map or the cards.

**Build order (summary):**

| Phase | Outcome |
|---|---|
| 0 | Foundation: repo hygiene, env/secrets, everything runs locally |
| 1 | **The Bridge**: both BRIDGE-CONTRACT-v1 receivers live; card deals appear as map pins |
| 2 | **The Brain**: TypeDB geo + archetype knowledge graph, additive over SQLite/Supabase/Mongo |
| 3 | **The Voice**: old build's voice grammar ported into llx11's MicWave, answers via LOOPER |
| 4 | **Jarvis**: Ricky desktop bot gets LocalLoop tools; map gets deep-link control |
| 5 | Card ↔ map business features: approval UI, View-card popups, archetype assist |
| 6 | News → geo-locked audio (podcast worker + PostGIS geofence) |
| 7 | **loop-onboard** (NEW repo): multi-district Facebook onboarding bot + admin rev-share |
| 8 | Multi-district Explore UI: district switcher, "Start a Local Loop" |
| 9 | Coolify deploy, cron, smoke tests, go-live flag flips |

---

## 2. The Three Systems Today (verified current state)

### 2.1 LOOPER (this repo)

- `looper-bot/` — "Ricky" Electron app. OpenAI **Realtime API over WebRTC**
  (`electron/main.cjs` mints ephemeral tokens at
  `https://api.openai.com/v1/realtime/client_secrets`; renderer connects via
  `src/lib/realtime.ts` to `/v1/realtime/calls`, data channel `oai-events`).
  23 model-facing tools (artifacts, web search via Exa, image/thumbnail
  generation, notes/records JSON DB, macOS computer control, screenshots).
  Animated face (`RickyFace.tsx`) lip-synced from output audio RMS.
  Local data: `data/ricky-db.json` (JSON, not SQLite).
- `backend/` — FastAPI, SQLite `data/looper.db`. Endpoints (all `/api`):
  `POST /onboard`, `GET /code/{code}`, `GET /search`, `GET /businesses`,
  `POST|GET /reviews`, `POST|GET /pins`, `GET /tourist-info`, plus `/health`.
  Models: `users`, `businesses` (has **`hybrid_card_id`** column — the bridge
  key, currently never populated), `reviews`, `map_pins`, `training_log`
  (never written — F2.5 fixes). Seeded with 20 Bondi businesses, 11 reviews.
  `services/facebook_pipeline.py` — Graph-API/demo importer that classifies
  group posts into reviews (works in `--demo` mode without a token).
- `web/looper-widget.js` — embeddable chat widget calling `GET /api/search`
  (API base hardcoded `http://localhost:8000/api` — F3.3 makes configurable).
- CORS already allows `https://localloop.pro`, `https://www.localloop.pro`,
  `https://explorer.localloop.ai`, localhost 3000/5173.
- Known drift: `README.md` names files that don't exist yet
  (`backend/services/review.py`, `matching.py`, `training.py`, `hermes/`,
  `training/finetune.py`). Trust the file tree.

### 2.2 LocalLoop Explore v11 (`llx11/localloop.pro-main`)

- **Static site, no backend framework.** `index.html` (~15k lines) is the
  canonical entry point (ADR-0003) — *surgical edits only, never rewrite*.
  Mapbox GL JS **v3.3.0**, custom styles
  (`mapbox://styles/localloop/ckzoopbp0001415n7ru8e4avo` primary), 3D
  building extrusions, pitch 58.
- **Supabase (Postgres + PostGIS)** via anon key + RLS:
  - `pin` — universal map record: `category pin_category` (**fixed set:**
    `News, Sales, Offers, Events, Accommodation, Job-Offers,
    Fetch_Deliveries, Food`), `tier` (`unregistered|freemium|premium` with
    heartbeats 1 hour / 1 week / 1 month), `coordinates GEOGRAPHY(POINT)`,
    `payload JSONB` (claims live here: `payload.source="claim-V1.html"`,
    `payload.moderation_status="pending_review"` → approved rows publish via
    the **`local_loop_business_layer`** view — ADR-0004/0006).
  - `app_user`, `news_post` (has `audio_url` + `feeder_id`), `news_feeder`.
- **looper-gateway** Cloudflare Worker (`workers/looper-gateway/`):
  `GET /health`, `GET|POST /mcp` (MCP tools: `looper_chat`,
  `map_search_proposal`, `pins_propose_create`, `business_report_stale`,
  `actions_confirm`), `POST /api/looper/chat`,
  `POST /api/looper/actions/confirm` (v1 refuses privileged writes), and the
  ONE real write: `POST /api/looper/pins/create` — Supabase **JWT-verified**
  (HS256 vs `SUPABASE_JWT_SECRET`), user bound to token `sub`, 50 pins/hr/user
  rate limit via KV, inserts `pin` with service role. Suggest-then-confirm
  everywhere (ADR-0005). Secrets: `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`; vars `ALLOWED_ORIGINS`.
- **Voice already exists (partial):** Picovoice Porcupine wake word
  ("Hey Looper") + Web Speech API single-shot recognition + the
  **Looper Response Panel / MicWave dock** (`plans/MicWave.md`,
  `assets/js/voice-listening-ui.js`, `assets/js/wake-word.js`, markup at
  `index.html` ~line 7146, `#ai-response*` ids, `LooperDock` component API,
  42-bar waveform). Voice commands today: ask-Looper text, category filters,
  radius, zoom-to-marker, `speakResponse()` TTS. **Duplicate logic warning:**
  unified search/voice logic exists in BOTH `assets/js/main-map.js` and the
  dock script — "keep in sync" (F3.2 extracts a shared router).
- **askSwarm bridge** (`js/localloop-swarm-bridge.js`): routes questions to
  the gateway (or Flowise on non-prod), parses a hidden `<map>{...}</map>`
  JSON tag from agent replies, geocodes the suburb, `flyTo`s the map, and
  renders Confirm/Cancel action cards.
- **News podcast:** `news-podcast-player.js` prefers `news_post.audio_url`,
  falls back to browser `speechSynthesis`. Audio *generation* job = not built
  (F6.1). News markers via `LocalLoopNewsMarkers`
  (source `localloop-news-markers`, layer `localloop-news-circles`).
- **Deploy:** Coolify on `167.86.79.151`, repo
  `localloop-pro/localloop.pro-main`, `npm start` (static serve :3000),
  health `/health.json` (static file), env injected at build by
  `scripts/inject-env.js` → `assets/js/env.js` (ADR-0002 — placeholders only
  in git). Live host **localloop.ai**; `localloop.pro` currently broken
  (Traefik default cert / 503) — fixed in F9.1.
- **House rules:** FollowMe.md lock protocol, confirm-first autonomy, ADRs in
  `SPEC/decisions.md`, no new top-level deps without justification, pin
  contract (`SPEC/pin-webhook-contract.md`) is load-bearing.

### 2.3 HybridCard (`hybridcard.ai/new-card`) — the SENDER

- Next.js 16 (App Router) + React 19 + Mongoose (`v2_*` collections) +
  BetterAuth + Vercel AI SDK. Deployed on Coolify (standalone Docker,
  health `GET /api/health`).
- 10 **archetypes** (food, accommodation, retail, health, trades,
  professional [+software-ai], events, creative, driver, other) drive tools,
  alert tags, JSON-LD, and skills.
- **The bridge is BUILT on the card side** (Phase 8 + 8.5, frozen):
  transactional outbox `v2_outbox` → cron `POST /api/internal/bridge/drain`
  (every 1 min, `x-cron-secret`) → HMAC-POSTs to receivers with headers
  `X-HC-Signature: sha256=<hex>`, `X-HC-Key-Id: hc-1`, `X-HC-Timestamp` (ms);
  signature base = `timestamp + "." + rawBody`; retry ALL non-2xx,
  backoff `min(30s·2^n, 6h)`, dead-letter after 6.
  Events: `deal.upserted` / `deal.removed` (⇒ `active` true/false).
  **Receivers must be idempotent on `eventId` and replay-tolerant.**
  Unset receiver URLs ⇒ events stay `pending` (safe today).
- Payloads (frozen — see `planning/BRIDGE-CONTRACT-v1.md`):
  - **LocalLoop MarkerPayload** (camelCase) → `POST {LOCALLOOP_BRIDGE_URL}/pin`:
    logo pin + `markerSize` by discount (≤10 small / 11-25 medium /
    26-50 large / ≥51 supersized), `claimUrl = https://<slug>.hybridcard.ai`,
    `vipCount` aggregate only.
  - **LooperIngestPayload** (snake_case) → `POST {LOOPER_INGEST_URL}`
    (canonical `https://localloop.ai/api/ingest/hybridcard-deal`):
    `hybrid_card_id`, `deal_id`, `category`, `discount_size`
    (**marker sizing only**), `rank_boost: false` (**always**).
  - Planned extension (T2 spec): `event_kind:'card'` payloads via
    `LOOPER_CARD_INGEST_URL` for card lifecycle (`card.upserted/removed`).
- **Anti-bias invariant (NON-NEGOTIABLE):** ranking = reviews + recency +
  proximity ONLY. Never rank by discount, source, or payment.
- **Privacy invariant:** payloads never contain PII/VIP identities/keys.
- Archetype→category map (§5 of contract): food→café, accommodation→
  accommodation, retail→shop, health→health, trades→trades, professional→
  professional, events→**event** (pinType `event`), creative→creative.
- Related shipped features: VIP member pass (vCard + QR + HMAC verify +
  redeem), live-alert tags (dry-run fan-out), Polar wallet + 1.8% AI
  metering, BYOK vault, ACMA SMS compliance. Hot-zone flags all OFF pending
  owner sign-off (`PAYMENTS_LIVE`, `SMS_LIVE`, `LIVE_ALERT_FANOUT`, VAPID).

### 2.4 The old voice build (port SOURCE only — never deploy)

`localloop.ai/golive_LocalLoop_Explore_html/explore-local.tsx` (single 1331-line
React component, Mapbox GL 3.24.1):

- Voice in: Web Speech API `SpeechRecognition` (`continuous: true`,
  `interimResults: true`), toggle start/stop; **intent runs on stop** over the
  full transcript.
- Intent router `processTranscript()`: keyword matching + one regex.
  Grammar worth porting: "stop"; radius ("1 km/2 km/3 km", "near me");
  category + subcategory matching over a taxonomy; **specific-business regex**
  `/(?:find|show|tell me about) ([\w\s]+)/i` → `flyTo(zoom 17)`; natural
  synonyms (hungry/eat→food, stay/sleep/hotel→accommodation,
  spa/relax/fitness→health, job/work→jobs); best offer ("offer","deal");
  booking intent. After intent: `fitBounds` over matching pins
  (`padding 50, maxZoom 15`) + spoken summary ("N options within X km").
- Voice out: `speechSynthesis`, rate 0.9 / pitch 1.1, **chunks >200 chars**
  (Chrome cutoff bug), `cancel()` on barge-in.
- Known bugs to port-FIX: stale-closure radius (reads old radius same tick);
  `includes("stop")` substring misfire; no `.lang`, no `onerror`; markers
  managed by DOM query `.mapboxgl-marker` (brittle).
- Constraints: HTTPS-only mic, Chrome/Edge/Safari (NOT Firefox), SSR-hostile
  (guard `typeof window`).

### 2.5 Facebook communities

- Bondi Local Loop: private group, **156.3K members**, ~7+ member requests
  visible/day, Admin Assist active (6 actions, 13 criteria), 3 membership
  questions already asked: (1) Bondi's most famous public pool (local check),
  (2) **email + reason for joining**, (3) how they heard / referrer name.
- Byron Bay Local Loop: ~6K members. More districts wanted: Rose Bay,
  Bronte, Maroubra, Bondi Junction, etc. — run by other admins who should
  earn a revenue share (see Phase 7).
- Media entities monitor the group for breaking local news → feeds the news
  layer (Phase 6).

---

## 3. Target Architecture

```
                       ┌────────────────────────────┐
                       │        HYBRIDCARD          │  (Next.js 16 + Mongo, Coolify)
                       │  cards · deals · archetypes│
                       │  VIP passes · BYOK AI      │
                       └─────┬───────────────┬──────┘
              outbox drain   │ HMAC X-HC-*   │ HMAC X-HC-*
              (cron, 1 min)  ▼               ▼
        ┌─────────────────────────┐   ┌──────────────────────────┐
        │  LOOPER API (FastAPI)   │   │  looper-gateway (CF wkr) │
        │  /api/ingest/…-deal  F1.1│   │  /api/bridge/pin     F1.3│
        │  /api/ingest/…-card  F1.2│   │  (draft pin, moderated)  │
        │  search · reviews · brain│   └──────────┬───────────────┘
        └───────┬───────────┬─────┘              │ service role
                │           │                     ▼
     TypeDB sync│           │            ┌─────────────────────┐
        (F2.2)  ▼           │            │  SUPABASE (PostGIS) │
        ┌──────────────┐    │            │  pin · news_post ·  │
        │   TYPEDB     │    │            │  app_user · views   │
        │ geo hierarchy│    │            └──────────┬──────────┘
        │ + archetypes │    │                       │ anon key + RLS
        │ + telemetry  │    │                       ▼
        └──────────────┘    │            ┌──────────────────────────┐
                            └───────────▶│  LOCALLOOP EXPLORE v11   │
                    /api/search (F3.3)   │  index.html + Mapbox GL  │
                                         │  MicWave voice (F3) ·    │
   ┌──────────────┐   looper tools (F4)  │  LooperMapBus (F3.4) ·   │
   │ RICKY desktop│◀───────────────────▶│  hybrid pins (F1.4) ·    │
   │ (Electron)   │                      │  news podcast (F6) ·     │
   └──────────────┘                      │  districts (F8)          │
                                         └──────────▲───────────────┘
   ┌──────────────────────────┐  member funnel      │
   │ LOOP-ONBOARD (NEW, F7)   │─────────────────────┘
   │ FB member intake · email │
   │ district admins · rev-share
   └──────────────────────────┘
```

**Datastore roles (decided, per TYPEDB-GEO-HIERARCHY-SPEC):**
MongoDB (cards), Supabase (map/news), SQLite (looper) stay the transactional
sources of truth. **TypeDB is ADDITIVE** — the relationship/knowledge layer:
DB 1 = geo hierarchy (World→Country→State→City→Suburb→Locality) + business
entities + archetype/skill graph; DB 2 = self-improving workflow telemetry.
Every TypeDB entity carries its FK back to the source system
(`mongo_card_id`, `hybrid_card_id`, `pin.id`).

**Contracts (all pre-existing, all frozen — extend, never contradict):**

| Contract | Where | Governs |
|---|---|---|
| BRIDGE-CONTRACT-v1 | `new-card/planning/` | HybridCard → receivers (HMAC, payloads, retries) |
| LOCALLOOP-BOT-GATEWAY-CONTRACT-v1 | `new-card/planning/` | bot scopes, proposals, approvals, audit |
| pin-webhook-contract | `llx11/…/SPEC/` | n8n pin intake fallback payloads |
| business-truth-layer (ADR-0006) | `llx11/…/SPEC/` | only approved claims publish |
| TYPEDB-GEO-HIERARCHY-SPEC | `new-card/planning/` | TypeQL schema + sync + migration phases |

---

## 4. Golden Rules (every feature below obeys these)

1. **Anti-bias:** rank by reviews + recency + proximity ONLY. `rank_boost`
   is always `false`. Discounts size markers, never rankings. Never say
   "the best" — always show multiple options.
2. **Public-safe:** no PII in any cross-system payload. Aggregate counts only.
3. **Frozen contracts:** receivers adapt to BRIDGE-CONTRACT-v1 exactly
   (HMAC over raw body, constant-time compare, ±5-min window, idempotent
   upsert on `eventId`, `active:false` = deactivate not delete).
4. **Bots never write production DBs directly** — gateway endpoints with
   auth, idempotency keys, audit logs, suggest-then-confirm (ADR-0005).
5. **`index.html` is sacred** — surgical, additive edits only (ADR-0003).
6. **No secrets in git** — runtime injection (`scripts/inject-env.js`,
   Coolify secrets, `wrangler secret put`). Existing secret-scan test stays
   green.
7. **Moderation before visibility** — hybridcard pins enter as drafts and an
   admin approves them before the public map shows them (ADR-0006 pattern).
8. **Confirm-first autonomy** — structural changes, new dependencies, or
   anything touching payments/SMS/real messages needs Bill's OK first.
9. **Every feature ends with copy-paste verify steps a beginner can run.**

---

## 5. Feature Sequence (implement strictly in this order)

> **Per-feature working files:** this section is split verbatim into
> `plans/features/01-foundation.md` … `10-deploy.md` (2026-07-11), each with
> its own checklist. Work from those files; this master plan stays
> authoritative if they ever disagree.

### Phase 0 — Foundation (blocks everything)

---

**F0.1 — Repo scaffolding + knowledge base (looper)**

- **What:** Add `plans/` (this file), `SEED.md`, `.SEED/decisions.md`,
  `.SEED/gotchas.md`, `AGENTS.md`, `CLAUDE.md` (→ `@AGENTS.md`) to the looper
  repo, matching the llx11 / new-card convention.
- **Why:** every coding agent orients from SEED.md first; rules stop agents
  breaking the frozen contracts.
- **Files:** `SEED.md`, `.SEED/*`, `AGENTS.md`, `CLAUDE.md`,
  `plans/IMPLEMENTATION_PLAN.md` (all new).
- **Steps:** files are already authored (this session) — commit them on
  branch `plan/bridge-v1`, push, open PR titled "Bridge master plan + SEED".
- **Acceptance:** `git log` shows the commit; SEED.md renders on GitHub;
  README quick-start still accurate.
- **Depends:** nothing.

---

**F0.2 — Everything runs locally (one command each)**

- **What:** Verified local bring-up of all three systems + document it in
  looper `README.md` ("Run the ecosystem locally" section).
- **Steps (junior-dev level):**
  1. looper backend: `cd backend && pip install -r requirements.txt &&
     python seed.py && python main.py` → check `http://localhost:8000/health`
     returns `{"status":"healthy"}` and `/docs` shows all routes.
  2. llx11: `cd llx11/localloop.pro-main && npm ci && npm start` → check
     `http://localhost:3000/health.json` (static file) and the map loads
     (needs `MAPBOX_TOKEN` in `.env` → `npm run prestart` injects
     `assets/js/env.js`).
  3. new-card: `cd hybridcard.ai/new-card && npm ci && npm run dev` (needs
     local Mongo, `MONGODB_URI` in `.env.local`) → `GET /api/health`.
  4. looper-bot (optional check): `cd looper-bot && npm ci && npm run dev`
     (needs `OPENAI_API_KEY` in `.env.local`).
- **Acceptance:** all three health checks green on one machine; README
  section exists with the exact commands above.
- **Depends:** F0.1.

---

**F0.3 — Secrets + env master table (generate once, store in Coolify + local `.env`s)**

- **What:** Create every shared secret the bridge needs; write
  `looper/.env.example` documenting them (placeholders only).
- **Steps:**
  1. Generate (never commit): `openssl rand -hex 32` × 4 →
     `HYBRIDCARD_INGEST_SECRET` (Looper receiver), `LOCALLOOP_BRIDGE_SECRET`
     (pin receiver), `CRON_SECRET` (already used by new-card), plus a spare.
  2. Add to `looper/.env.example`: `LOOPER_PORT`, `LOOPER_DB_URL`,
     `HYBRIDCARD_INGEST_SECRET`, `HYBRIDCARD_KEY_IDS=hc-1`,
     `TYPEDB_ENABLED=false`, `TYPEDB_ADDRESS=localhost:1729`,
     `LOOPER_PUBLIC_API_BASE` (for the widget), `NEWS_TTS_PROVIDER`/key
     (Phase 6).
  3. Record where each lives (Section 7 table): looper Coolify service,
     new-card Coolify service, Cloudflare worker secrets, llx11 build env.
- **Acceptance:** `.env.example` committed; secrets exist in a password
  manager + Coolify; nothing real in git (secret-scan test green).
- **Depends:** F0.1.

---

**F0.4 — Dockerize the looper backend**

- **What:** `looper/backend/Dockerfile` + repo-root `docker-compose.yml`
  (service `looper-api`, port 8000, volume for `data/looper.db`), matching
  the Coolify pattern used by llx11 (`python:3.12-slim`, `uvicorn
  main:app --host 0.0.0.0 --port 8000`, `HEALTHCHECK` on `/health`).
- **Acceptance:** `docker compose up` → `curl localhost:8000/health` green;
  restart container → seeded data persists (volume works).
- **Depends:** F0.2.

---

### Phase 1 — The Bridge: receivers live (HybridCard → map + brain)

---

**F1.1 — Looper deal-ingest receiver (`POST /api/ingest/hybridcard-deal`)**

- **What:** The FastAPI receiver for **LooperIngestPayload** (frozen §3b of
  BRIDGE-CONTRACT-v1). This is the single most important missing piece —
  HybridCard is already trying to send to it.
- **Files (new):** `backend/routes/ingest.py`,
  `backend/services/bridge_hmac.py`, `backend/models.py` (add two tables),
  `backend/tests/test_ingest.py`.
- **Steps:**
  1. `bridge_hmac.py`: `verify(raw_body: bytes, headers) -> key_id`.
     Recompute `HMAC_SHA256(secret, f"{ts}.{raw}")` where secret is looked up
     by `X-HC-Key-Id` from env `HYBRIDCARD_INGEST_SECRET` (support a dict for
     future key rotation, default id `hc-1`). Constant-time compare
     (`hmac.compare_digest`). Reject: unknown key id, non-numeric ts,
     `abs(now_ms - ts) > 300_000`. IMPORTANT: read the RAW request body
     before Pydantic parsing (`await request.body()`).
  2. New models: `bridge_events` (`event_id` UNIQUE, `target`, `payload`
     JSON, `received_at`, `status`) and `deals` (`deal_id` UNIQUE,
     `business_id` FK, `title`, `short_description`, `category`, `pin_type`,
     `sub_type`, `discount_size`, `lat`, `lng`, `hours`, `public_card_url`,
     `active`, `updated_at`).
  3. Route logic (idempotent): if `event_id` already in `bridge_events` →
     return `200 {"ok":true,"duplicate":true}`. Else upsert `businesses`
     keyed on **`hybrid_card_id`** (create with `source="hybrid_card"`,
     update name/category/lat/lng), upsert `deals` on `deal_id`, set
     `active` from payload (`deal.removed` ⇒ `active=false`, never delete),
     record event, return 200 ONLY after commit.
  4. Never use `discount_size` or `source` in search ranking
     (`routes/search.py` untouched — add a code comment + test asserting
     ranking inputs).
- **Acceptance (must all pass in `pytest`):**
  - valid signed payload → 200, business + deal rows exist;
  - same `eventId` replayed → 200, still exactly one row each;
  - bad signature / stale timestamp / unknown key id → 401, no rows;
  - `deal.removed` → `deals.active=false`, row NOT deleted;
  - a business search never orders by discount (anti-bias test).
  - Manual: `python tests/send_signed_event.py` helper script (write it)
    posts a sample payload with a locally generated signature.
- **Depends:** F0.3, F0.4.

---

**F1.2 — Looper card-ingest receiver (`POST /api/ingest/hybridcard-card`)**

- **What:** Receiver for the T2 card-lifecycle payloads
  (`event_kind:'card'`, `card.upserted` / `card.removed`) so every published
  card (not just deals) becomes a LOOPER business. HybridCard's env for this
  is `LOOPER_CARD_INGEST_URL`.
- **Steps:** same HMAC module; upsert `businesses` on `hybrid_card_id` with
  `name`, `category` (mapped via contract §5), `lat/lng`, `website =
  public_card_url`; `active:false` ⇒ `is_verified` stays, business flagged
  inactive (add `is_active` column).
- **Acceptance:** same idempotency/HMAC matrix as F1.1; card unpublish
  deactivates the business and its deals stop appearing in `/api/search`.
- **Depends:** F1.1.

---

**F1.3 — LocalLoop `/pin` receiver (looper-gateway worker)**

- **What:** Receiver for **MarkerPayload** (frozen §3a) that turns card deals
  into *draft* Supabase `pin` rows awaiting approval. Lives in the existing
  Cloudflare Worker (Phase-18A decision: `localloop.pro-main` owns it).
  Endpoint: `POST /api/bridge/pin` — and set HybridCard's
  `LOCALLOOP_BRIDGE_URL` so `/pin` resolves here (e.g.
  `https://looper.localloop.ai/api/bridge` → worker route appends `/pin`).
- **Files:** `workers/looper-gateway/src/bridge-pin.mjs` (new),
  `src/index.mjs` (route), `wrangler.jsonc` (new secret
  `LOCALLOOP_BRIDGE_SECRET`), `tests/looper-gateway-bridge-pin.unit.js`.
- **Steps:**
  1. HMAC verify exactly as F1.1 (raw body, `X-HC-*`, ±5 min, constant-time
     — reuse the worker's existing timing-safe compare helper).
  2. Map payload → `pin` row: `category` from contract category →
     pin_category (**mapping table:** café→`Food`, accommodation→
     `Accommodation`, event→`Events`, everything else→`Offers`),
     `tier: 'premium'` (cards are paying businesses),
     `coordinates: SRID=4326;POINT(lng lat)`,
     `payload: { source: "hybridcard", moderation_status: "pending_review",
     event_id, deal_id, hybrid_card_id, slug, business_name, logo_url,
     marker_size, discount_pct, title, short_description, claim_url,
     vip_count, rating, hours, expires_at }`.
  3. Idempotent upsert: SELECT by `payload->>deal_id`; update if exists
     (including `active:false` ⇒ set `payload.moderation_status='removed'`
     and expire the pin), else INSERT via service role (reuse the PostgREST
     pattern from `pin-write.mjs`).
  4. Return 2xx only on durable success (the sender retries all non-2xx).
  5. Do NOT bypass moderation: drafts stay invisible until F5.2 approval.
- **Acceptance:** unit tests (mock fetch to PostgREST) for HMAC matrix +
  idempotent upsert + category mapping + deactivate; `wrangler dev` manual
  signed POST creates a pending pin visible in Supabase table editor and
  NOT on the public map.
- **Depends:** F0.3 (secret), F1.1 (shared HMAC vector fixtures — reuse the
  same test vectors so both receivers agree byte-for-byte).

---

**F1.4 — HybridCard pins render on the Explore map**

- **What:** Approved hybridcard pins show as logo markers sized by
  `marker_size`, with a popup: business name, title, discount, ⭐ rating,
  VIP count, and **"View card →" linking `claimUrl`**
  (`https://<slug>.hybridcard.ai`).
- **Files:** `assets/js/hybridcard-markers.js` (new, follows the
  `simple-news-markers.js` wrapper pattern), one `<script>` include +
  `_redirects` check in `index.html` (surgical), small CSS block.
- **Steps:** query the `local_loop_business_layer`-style path: select `pin`
  where `payload->>source = 'hybridcard'` AND `payload->>moderation_status
  IN ('approved','published')` AND active; render Mapbox markers (logo image
  with fallback dot; size map small=28px / medium=38px / large=48px /
  supersized=64px); popup template; refresh on `map.moveend` within
  viewport bounds.
- **Acceptance:** seed one approved test pin → marker renders at correct
  size; popup "View card →" opens the card subdomain in a new tab;
  pending/removed pins never render; Lighthouse perf unchanged (>90).
- **Depends:** F1.3.

---

**F1.5 — End-to-end bridge dry run (staging)**

- **What:** Prove the whole pipe: new-card outbox → drain cron → both
  receivers → approval → map pin, on staging URLs.
- **Steps:** deploy F0.4 + F1.x to staging (Phase 9 gives the full recipe;
  a minimal staging is enough here); set `LOOPER_INGEST_URL` +
  `LOCALLOOP_BRIDGE_URL` + secrets in the new-card staging env; create a
  test deal in HybridCard; run drain
  (`curl -X POST …/api/internal/bridge/drain -H "x-cron-secret: $CRON_SECRET"`);
  approve the draft pin; see the marker.
- **Acceptance:** outbox event goes `pending→sent` (not `dead`); looper
  `businesses.hybrid_card_id` populated; pin approved → visible in <1 min;
  `deal.removed` → marker disappears + looper deal inactive. Record evidence
  screenshots in `plans/evidence/F1.5/` (agent-collab style).
- **Depends:** F1.1–F1.4.

---

### Phase 2 — The Brain: TypeDB knowledge graph (ADDITIVE)

---

**F2.1 — TypeDB service + geo schema**

- **What:** TypeDB container (Coolify, internal-only port 1729) + schema
  001 (geo) + 002 (business) from TYPEDB-GEO-HIERARCHY-SPEC, seeded for AU:
  NSW → Sydney → Eastern-Suburbs suburbs (Bondi, Bondi Junction, Bronte,
  Rose Bay, Maroubra, …) + Byron Bay; pre-computed `nearby` relations
  (10 km default).
- **Files (looper repo):** `brain/schema/001_geo.tql`,
  `brain/schema/002_business.tql`, `brain/seed_geo.py`,
  `brain/migrate.py` (tracks applied schema files), `brain/README.md`.
- **Steps:** run TypeDB via docker (`vaticle/typedb`, database `localloop`;
  staging `localloop_staging`); define abstract `geo_region` + concrete
  world/country/state/city/suburb/locality; `located_in`, `nearby`
  (with `distance_km`); `business_entity` (owns `hybrid_card_id`,
  `source_pin_id`, name, slug, archetype_id, sub_type, tier, is_active) +
  `serves_area`, `franchise_of`, `subsidiary_of`. Seed suburbs from a
  committed CSV (name, postcode, lat, lng) — start with ~20 eastern-suburbs
  rows + Byron Bay, not all of GNAF.
- **Acceptance:** `python brain/migrate.py && python brain/seed_geo.py`
  idempotent; TypeQL query "suburbs within 5 km of Bondi" returns Bronte +
  Bondi Junction; port 1729 NOT publicly reachable.
- **Depends:** F0.4 (docker patterns); parallel-safe with Phase 1.

---

**F2.2 — Sync worker: bridge events + SQLite → TypeDB**

- **What:** Whenever a business/deal lands (F1.1/F1.2) or on nightly full
  sync, upsert the matching `business_entity` + `located_in` (nearest
  suburb by haversine over the seeded suburb list) into TypeDB. TypeDB down
  ⇒ log and continue (never block ingest — additive rule).
- **Files:** `brain/sync.py` (uses `typedb-driver` Python), hook in
  `routes/ingest.py` (fire-and-forget task via FastAPI `BackgroundTasks`),
  `brain/full_sync.py` (CLI, cron nightly).
- **Acceptance:** ingest a signed test deal → TypeDB has the business with
  `located_in Bondi`; stop TypeDB container → ingest still returns 200;
  `full_sync.py` backfills the 20 seeded businesses.
- **Depends:** F1.1, F2.1.

---

**F2.3 — `/api/discover` (graph-powered search with safe fallback)**

- **What:** New looper endpoint
  `GET /api/discover?suburb=Bondi&radius_km=5&category=food` — TypeDB
  resolves the geo set (`nearby` suburbs → businesses), SQLite hydrates
  details + reviews, ranking stays reviews+recency+proximity. If
  `TYPEDB_ENABLED=false` or TypeDB errors → transparent fallback to the
  existing haversine query (identical response shape, plus
  `"engine": "fallback"`).
- **Acceptance:** parity test: fallback vs graph return the same businesses
  for the seeded set; response includes `engine` field; anti-bias test
  passes (no discount in ordering).
- **Depends:** F2.2.

---

**F2.4 — Archetype + skill graph (category assist)**

- **What:** Schema 004: `archetype`, `archetype_sub_type`,
  `skill_definition`, relations `has_sub_type`, `provides_skill`,
  `inherits_skills`. Seed the 10 HybridCard archetypes + the per-archetype
  skill lists from ARCHETYPE-SKILL-REGISTRY-SPEC (55 skills as data — names,
  categories, NOT the prompts; prompts stay in the card repo).
  Endpoint: `GET /api/archetypes/{archetype}/skills?sub_type=…` returning
  the resolved skill set (sub-type overrides → inherited archetype skills).
- **Why:** this is how Looper "helps business category types better their
  business through their card" — it can tell any business what its card can
  do for it, and llx11/Ricky can surface it.
- **Acceptance:** `GET /api/archetypes/trades/skills?sub_type=plumber`
  returns plumber-specific + inherited trades skills, deduped; unknown
  archetype → 404.
- **Depends:** F2.1 (F2.2 not required).

---

**F2.5 — Self-improving telemetry (finally write `training_log`)**

- **What:** Log every `/api/search`, `/api/discover`, and widget/voice query
  into the existing `training_log` table (query, response summary, intent,
  session_id — NO PII, no mobile numbers) + per-archetype counters into
  TypeDB DB 2 (`workflow_telemetry` schema 005: skill/category usage counts
  by archetype). `training/export.py` then has real data → JSONL for the
  future fine-tune loop.
- **Acceptance:** 10 test queries → 10 `training_log` rows with intents;
  `python training/export.py` emits valid JSONL; a `grep`-based test proves
  no mobile numbers/emails in exports.
- **Depends:** F2.3 (F2.4 for archetype counters).

---

### Phase 3 — The Voice: old-build grammar into llx11's MicWave

> llx11 ALREADY has: "Hey Looper" wake word (Porcupine), Web Speech
> single-shot recognition, the MicWave dock UI, basic category/radius/zoom
> commands, `speakResponse()` TTS, and `askSwarm()` with a `<map>` tag →
> suburb flyTo. Phase 3 does NOT rebuild any of that — it unifies it and
> ports what the OLD build had that llx11 lacks.

---

**F3.1 — Voice gap audit (evidence first, code second)**

- **What:** A written checklist comparing the old build's grammar (§2.4)
  against llx11's current voice router(s) (`assets/js/main-map.js` +
  `assets/js/voice-listening-ui.js` — note the known "duplicate logic, keep
  in sync" warning in `plans/MicWave.md`).
- **Output:** `plans/evidence/F3.1-voice-gap-audit.md` in llx11 listing per
  command: works / missing / broken, with a screen recording of each.
- **Expected gaps (verify, don't assume):** specific-business "find/show/
  tell me about X" regex → flyTo; radius phrase parsing ("within 2 km",
  "near me"); natural synonyms (hungry/eat/stay/relax/work); best-offer
  intent; booking intent; fitBounds-over-category-results; TTS chunking for
  >200-char replies; barge-in cancel; explicit "zoom in/out/reset" verbs
  (old build lacked them too — add new).
- **Acceptance:** checklist reviewed by Bill; each gap becomes a checkbox
  F3.2 must tick.
- **Depends:** F0.2 (llx11 running locally). Parallel-safe with Phases 1–2.

---

**F3.2 — Shared voice command router (one grammar, both entry points)**

- **What:** Extract `assets/js/voice-command-router.js` (new, framework-free
  IIFE like the site's other modules): input = final transcript string +
  context (map center, active category, radius); output = a **command
  object** `{intent, category?, subcategory?, radiusM?, businessName?,
  suburb?, speak?:string}` — NO direct map calls inside the router (pure,
  unit-testable).
  Port from the old build (with fixes): stop (word-boundary regex, not
  substring), radius parsing incl. "near me" → 1000 m, category + synonym
  table mapped to the **fixed pin categories** (hungry/eat → `Food`,
  stay/hotel → `Accommodation`, deal/offer → `Offers`, job/work →
  `Job-Offers`, news → `News`, event → `Events`, delivery/courier →
  `Fetch_Deliveries`), specific-business regex, best-offer, booking intent,
  "take me to <suburb>" (delegates to the existing askSwarm geocode path),
  NEW: "zoom in/out", "reset view". Fix the stale-radius bug: the command
  object carries the parsed radius, consumers never read stale state.
  Wire BOTH existing entry points (`main-map.js` handler + MicWave dock) to
  this one router; delete the duplicated logic.
- **Files:** `assets/js/voice-command-router.js` (new),
  `tests/voice-command-router.unit.js` (new, node-runnable like the
  gateway's unit tests), surgical call-site swaps in `main-map.js` +
  `voice-listening-ui.js`, `<script>` include in `index.html`.
- **Acceptance:** unit tests cover ≥25 utterances → expected command
  objects (including the misfire case: "bus stop near me" must NOT trigger
  stop); manual: the F3.1 checklist all green in Chrome; Firefox falls back
  to typed input without console errors.
- **Depends:** F3.1.

---

**F3.3 — Voice answers come from the LOOPER brain**

- **What:** When the router yields a search-like intent, call the LOOPER API
  (`/api/search` or `/api/discover` with lat/lng/radius/category), then
  (a) SPEAK an anti-bias summary ("I found 4 cafés within 1 km — Gertrude &
  Alice has 5 stars from 12 reviews…", chunked >200 chars, cancel on
  barge-in), and (b) act on the map via the bus (F3.4): drop/refresh result
  pins, `fitBounds` over them (padding 50, maxZoom 15).
  Make the widget/API base configurable:
  `window.LocalLoopConfig.looperApi` (exists) — default
  `https://api.localloop.ai` in prod injection, localhost:8000 in dev.
  Graceful degrade: LOOPER down → existing local search path (current
  behaviour), spoken apology.
- **Files:** surgical edits in the `handleAIQuery` integration area of
  `index.html` / `main-map.js`; `web/looper-widget.js` in looper repo (read
  API base from config instead of hardcoded localhost).
- **Acceptance:** say "find me a café" → spoken multi-option answer with
  review counts + map fits bounds to those pins; kill looper-api → same
  utterance still answers from local search; no ranking by discount
  anywhere.
- **Depends:** F3.2 (+ F2.3 optional — works against `/api/search` alone).

---

**F3.4 — `LooperMapBus`: one documented control surface for the map**

- **What:** `assets/js/looper-map-bus.js` (new) exposing
  `window.LooperMapBus = { setCategory(cat), flyTo(lng, lat, zoom?),
  fitCategory(cat, radiusM?), zoom(delta), reset(), showBusiness(idOrName),
  openNews(id) }` — thin wrappers around the existing map + marker systems.
  Voice router consumers, `askSwarm`'s `<map>` tag handler, gateway client
  actions (`map.search`), and F4.2 deep links ALL call the bus instead of
  poking `window.localloopMap` directly.
- **Why:** today three code paths each drive the map their own way; the bus
  makes voice/bot control testable and stops regressions.
- **Acceptance:** every bus method callable from DevTools console with
  visible effect; askSwarm suburb flyTo still works (now via bus); unit
  smoke test with a mocked map object.
- **Depends:** F3.2 (can land together).

---

### Phase 4 — Jarvis: Ricky ↔ the ecosystem

---

**F4.1 — Ricky gets LocalLoop tools**

- **What:** Add model-facing tools to `looper-bot/electron/main.cjs`
  `toolSpecs` + `tools:execute`: `localloop_search` (GET
  `{LOOPER_API_BASE}/api/search`), `localloop_discover` (F2.3),
  `localloop_archetype_skills` (F2.4), `localloop_pins` (GET /api/pins),
  `localloop_gateway_health` (GET gateway `/health`), each returning an
  artifact (table/markdown) for the ArtifactPanel. Add `LOOPER_API_BASE` to
  `.env.local` handling (default `http://localhost:8000`).
  Update `RICKY_INSTRUCTIONS` so Ricky knows: it is LOOPER's desktop face;
  anti-bias rules; when asked about local businesses it MUST use the tools,
  present multiple options, and never invent ratings.
- **Acceptance:** ask Ricky "what's good for lunch in Bondi?" → it calls
  `localloop_search`, artifact panel shows an options table with ⭐ counts,
  voice answer names ≥2 options; tools fail gracefully offline.
- **Depends:** F0.2 (backend running); better after F2.3/F2.4.

---

**F4.2 — Map deep links (`?cat=…&q=…&fly=lng,lat,zoom`)**

- **What:** llx11 `index.html` parses query params on load and routes them
  through `LooperMapBus` (category filter, search query into the Looper
  dock, camera). Ricky gets tool `localloop_open_map` that builds the URL
  and opens the browser (`open` on macOS).
- **Acceptance:** `https://localloop.ai/?cat=Food&fly=151.2743,-33.8908,16`
  opens filtered + positioned; Ricky "show me Bondi cafés on the map" opens
  exactly that URL.
- **Depends:** F3.4.

---

**F4.3 — Ricky bridge-ops cockpit (read-only v1)**

- **What:** Tools for Bill to ask "how's the bridge?": `bridge_status`
  (reads looper `GET /api/ingest/status` — add tiny endpoint returning last
  20 `bridge_events` + counts by status), `pending_pins` (Supabase count of
  hybridcard pins pending review, via gateway `GET /api/bot/map/pins?...`
  read-only path if enabled, else via looper proxy). NO write tools yet —
  writes wait for the gateway's Phase 18B approval flow.
- **Acceptance:** "Ricky, any card deals waiting for approval?" → correct
  count + table artifact; all calls read-only (verified by gateway audit
  log / code review).
- **Depends:** F1.5.

---

### Phase 5 — Card ↔ map business features

---

**F5.1 — Draft-pin approval UI (moderation queue)**

- **What:** An admin-only "Pending card pins" panel (extend the existing
  `dashboard.html`) listing pins where `payload->>source='hybridcard'` AND
  `moderation_status='pending_review'`: business, title, discount, preview
  location; Approve / Reject buttons.
  **Writes go through the worker, never the browser with service keys:**
  new endpoint `POST /api/admin/pins/moderate` in looper-gateway —
  Supabase-JWT-verified (reuse `pin-write.mjs` verifier) + user id must be
  in new worker var `ADMIN_USER_IDS`; body
  `{pin_id, decision: "approved"|"rejected"}`; sets
  `payload.moderation_status` accordingly; audit-logs the action.
- **Acceptance:** non-admin JWT → 403; approve flips the pin to visible on
  the map (F1.4 query picks it up) within one refresh; reject hides it
  permanently; every decision has an audit row.
- **Depends:** F1.3, F1.4.

---

**F5.2 — Claimed-business popups link to cards ("View card →")**

- **What:** Complete the agent-collab Phase C flow: approved claim pins
  (Business Truth Layer) whose payload carries `business_slug` (or a
  hybridcard match by name) show "View card →" → `/hybridcard/{slug}` page
  (hydrates from the moderated pin row; `_redirects` rule
  `/hybridcard/* /hybridcard.html 200` must exist), and card-side
  `claimUrl` pins (F1.4) link out to `https://<slug>.hybridcard.ai`.
- **Acceptance:** click a claimed business → popup shows the link; the
  `/hybridcard/{slug}` page renders name/category/contact from the pin; no
  pending row ever renders publicly.
- **Depends:** F1.4.

---

**F5.3 — "Get your Hybrid Card" funnel from the map**

- **What:** Unclaimed/unregistered business pins + the claim success screen
  get a CTA: "Own this business? Get your Hybrid Card" →
  `https://hybridcard.ai` onboarding (with `?src=localloop&district=<slug>`
  UTM so Phase 7 rev-share can attribute signups). Config-driven copy.
- **Acceptance:** CTA renders only for non-hybridcard pins; UTM params
  arrive on the card site (verify in its request logs); district param
  matches the active district (F8).
- **Depends:** F1.4 (F8.1 for district param — ship with `bondi` hardcoded
  first).

---

**F5.4 — Archetype assist surfaced to owners**

- **What:** In the popup for a hybridcard business (owner view / after
  claim), show "What your card can do" — the resolved skill list from
  `GET /api/archetypes/{archetype}/skills` (F2.4), e.g. a café sees
  menu-receptionist, daily-specials writer, review responder. Pure read-only
  discovery that drives owners into the card dashboard.
- **Acceptance:** popup for a `food` business lists the 7 food skills; API
  outage hides the section silently.
- **Depends:** F2.4, F5.2.

---

### Phase 6 — News → geo-locked audio (the podcast layer)

> Already built in llx11: news markers, `news.html`, the podcast player that
> PREFERS `news_post.audio_url` and falls back to browser TTS. Missing: the
> audio generator and the server-side geo lock.

---

**F6.1 — News audio worker (text → voice → `audio_url`)**

- **What:** A cron-driven worker that finds `news_post` rows with
  `audio_url IS NULL`, generates spoken audio (env-selected provider:
  start with OpenAI TTS `tts-1`, voice configurable; provider behind
  `NEWS_TTS_PROVIDER`/`NEWS_TTS_API_KEY`), uploads MP3 to a Supabase Storage
  bucket `news-audio` (public-read), and updates `audio_url`.
- **Files (looper repo):** `tools/news_audio_worker.py` (reads Supabase via
  service key from env — server-side only), Coolify Scheduled Task
  (`*/10 * * * *`), `tools/README.md`.
- **Steps:** intro line template "Local Loop <district> news, <date>:" +
  title + body (strip markdown/URLs); cap ~90 seconds; idempotent (skip
  rows already having audio); mark failures in `payload.audio_error` and
  move on.
- **Acceptance:** insert a test news post → MP3 exists in the bucket +
  `audio_url` set within 10 min → the EXISTING player plays it (no client
  changes needed); re-run does not regenerate.
- **Depends:** F0.3 (secrets). Parallel-safe with Phases 1–5.

---

**F6.2 — Server-side geo lock for news**

- **What:** News is only served near where it happened ("locals-only" rule).
  Create Supabase RPC `get_news_nearby(lat double, lng double,
  radius_m int default 5000)` using PostGIS `ST_DWithin` over
  `news_post.coordinates`, exposed to anon; switch `getNewsForMap()` /
  `news.html` to call the RPC with the browser's geolocation; RLS on
  `news_post` direct selects tightened so the RPC is the read path.
  No location permission ⇒ show teaser cards with a "share your location to
  listen" CTA (no audio).
- **Acceptance:** request with Bondi coords returns Bondi items; Byron
  coords return none of them; direct table select no longer returns bodies
  (RLS proof); UI CTA appears when geolocation denied.
- **Depends:** F6.1 (worker unaffected — parallel OK); coordinate with the
  llx11 rule "apply schema/RLS only against a confirmed non-production
  target" — staging first.

---

**F6.3 — Community sentiment tag on news (light-touch, P2)**

- **What:** Nightly job scores reader comments/reactions per news post with
  the same positive/negative word-count approach as
  `backend/services/facebook_pipeline.py` and writes
  `payload.sentiment: positive|neutral|negative` + counts; the news card
  shows a small mood chip. No heavy NLP, no PII.
- **Acceptance:** seeded comments produce the expected chip; job idempotent.
- **Depends:** F6.2.

---

### Phase 7 — `loop-onboard` (NEW repo): multi-district Facebook onboarding

> **Decision (recommended):** this is a NEW app in a NEW folder/repo
> `loop-onboard` — Bill creates the empty folder; the coding agent
> scaffolds it. It serves Bondi Local Loop first, but is **multi-district
> from day one** so Rose Bay / Bronte / Maroubra / Bondi Junction / Byron
> Bay admins can run their own funnel and earn their share.

---

**F7.1 — Scaffold `loop-onboard`**

- **What:** Next.js (same major version + conventions as new-card:
  TypeScript, App Router, Coolify standalone Dockerfile, `GET /api/health`)
  backed by **Supabase** (same project as the map — one community datastore).
  Tables (SQL migration in repo):
  `district` (slug, name, center_lat, center_lng, radius_m, fb_group_url,
  admin_name, admin_email, revshare_pct, status),
  `member` (id, district_slug FK, first_name, email UNIQUE-per-district,
  source `facebook|form|import`, fb_answers JSONB, referrer_name,
  consent_marketing bool, joined_fb_at, welcomed_at, card_claimed_at),
  `intake_log` (raw rows, idempotency key), `revshare_ledger` (district,
  period, attributed_signups, amount, status).
  Seed districts: bondi, byron-bay, rose-bay, bronte, maroubra,
  bondi-junction.
- **Acceptance:** `npm run dev` → health green; migration applies cleanly to
  staging Supabase; districts seeded.
- **Depends:** F0.3. Parallel-safe with everything.

---

**F7.2 — Member intake API + Facebook capture (verified July 2026 reality)**

- **Hard facts the design is built on (verified, sources in
  `.SEED/decisions.md`):** the Facebook **Groups API is dead** (removed
  April 2024 — no app can read member requests, answers, or approve
  members); membership-question answers are **only visible while a request
  is pending** (they vanish at approval, no export exists); Pages/apps
  **cannot cold-DM** members; Admin Assist can auto-approve + schedule
  welcome posts but can't capture or message.
- **What:** `POST /api/intake/member` — idempotent (hash of
  district+email+joined_fb_at), token-authenticated (`INTAKE_TOKEN` per
  district), accepting `{district, first_name, email, answers:{q1,q2,q3},
  referrer_name?, joined_fb_at, source}` — fed by THREE layers:
  1. **Layer 1 — official, zero risk, do immediately (no code):** reword
     membership Q2/Q3 so the email ask is explicit and opt-in ("Want the
     free Local Loop discount card? Leave your email"); Admin Assist
     auto-approves requests that answered all questions; weekly official
     Welcome Post (auto-tags up to 300 new joiners/7 days) + a pinned
     Admin-Assist recurring post, both linking to
     `join.localloop.ai/<district>` where email capture happens first-party
     with real consent.
  2. **Layer 2 — capture at approval (the main engine):** answers must be
     grabbed at the pending-request moment, in the admin's own browser.
     Options, same webhook target either way: Group Collector
     (~$297 lifetime, has webhooks + Sheets) / Groupboss (~$99/yr) — or a
     **self-built Chrome MV3 extension** (Bill has a dev account): a
     MutationObserver on the Member Requests page that, when the admin
     clicks Approve, POSTs the visible answers to `/api/intake/member`.
     Human-clicked approvals only (no bulk auto-approve), human pacing,
     dedicated Chrome profile, and prefer a second admin account for daily
     approvals — this technique breaches Meta ToS §3.2.3 in principle
     (risk = admin account restriction), though such tools have run for
     6+ years; Bill accepts/declines this trade-off explicitly.
  3. **Layer 3 — CSV/manual:** paste/upload page for anything captured by
     hand; always works, zero risk.
- **Acceptance:** posting the same member twice → one row; a CSV of 50 test
  rows imports with a per-row result report; invalid-email rows land in
  `intake_log` for manual fix, never crash; Layer 1 changes live in the
  Bondi group (screenshot evidence).
- **Depends:** F7.1.

---

**F7.3 — Welcome funnel (email-first)**

- **What:** On new member: send district-branded welcome email (provider:
  Resend or SMTP, env-driven; NO SMS in v1 — ACMA compliance lives in the
  card repo and is not re-solved here): "Welcome to <District> Local Loop —
  ① explore the local map (`localloop.ai/?district=<slug>`), ② claim your
  member discount card, ③ business owner? get your Hybrid Card
  (`hybridcard.ai?src=loop-onboard&district=<slug>`)."
  Member discount card v1 = a per-member QR page
  (`loop-onboard.../m/<member_code>`) reusing the VIP-pass verify pattern
  (HMAC-signed code) — full HybridCard VIP pass integration later.
  Double-entry consent: email footer unsubscribe + `consent_marketing`
  honored (Spam Act 2003: consent, identify sender, unsubscribe).
- **Acceptance:** test member → email arrives with working links + QR page
  renders; unsubscribe link flips consent and blocks further sends;
  `welcomed_at` set exactly once.
- **Depends:** F7.2.

---

**F7.4 — District admin console + revenue share**

- **What:** Login (Supabase Auth, email magic link) scoped per district:
  see member counts/conversion (welcomed → card claimed), edit welcome copy,
  upload CSVs, copy their intake token, view `revshare_ledger` (attributed
  hybridcard signups via the `?src=…&district=…` UTMs × `revshare_pct` —
  numbers visible from day one, payouts manual/monthly by Bill in v1).
- **Acceptance:** Bondi admin cannot see Byron data (RLS test); ledger shows
  a seeded attributed signup; copy edit changes the next welcome email.
- **Depends:** F7.3.

---

**F7.5 — Onboarding assistant (the "separate bot" for the group)**

- **What:** A LOOPER-brained chat endpoint + simple web chat on the welcome
  page ("Ask your Local Loop anything") that answers: what the group/map is,
  how the discount card works, how businesses join — powered by the looper
  API (search + archetype skills) with district context. Same
  suggest-then-confirm rules; it never messages anyone first.
- **Acceptance:** 10 scripted Q&A pairs answer correctly with district
  context; it refuses off-scope requests (no political content, no PII
  lookups).
- **Depends:** F7.3 (+F2.4 for business answers).

---

**F7.6 — "Comment CARD" Private-Reply bot (pilot — the ONLY compliant automated DM)**

- **What:** Meta kept exactly one group messaging path for apps: a Page can
  send **one Private Reply to a user's comment on a group post within
  7 days** (Page access token + `pages_messaging`, app subscribed to the
  `groups_feed` webhook field; private replies enabled in group settings).
  Build a tiny service in loop-onboard: welcome post says "Comment CARD and
  we'll DM you your Local Loop discount card" → webhook fires on comment →
  bot sends ONE private reply with the member-card link → if the user
  replies, the standard 24-hour window lets the bot collect their email
  conversationally.
- **Steps:** create the Meta app + Page token in Bill's dev account; App
  Review for `pages_messaging`; subscribe `groups_feed`; **validate with a
  test post first** — post-2024 webhook behaviour for groups is not
  well-documented in the wild, so this ships as a PILOT with a kill switch;
  log every send (one per commenter, ever) to stay inside policy.
- **Acceptance:** commenting CARD on the test post produces exactly one DM
  with a working card link; a second comment produces nothing; webhook
  outage degrades silently (welcome post still links to join page).
- **Depends:** F7.3. If the webhook proves dead, close the feature and note
  it in `.SEED/decisions.md` — Layers 1–3 carry the funnel.

---

### Phase 8 — Multi-district in the Explore app (make it OBVIOUS)

---

**F8.1 — District registry on the map site**

- **What:** llx11 reads the `district` table (anon read of approved rows):
  slug, name, center, radius. URL param `?district=<slug>` and a header
  **district switcher** (dropdown next to the logo: "Bondi · Byron Bay ·
  Rose Bay · …") that flies the camera to the district and scopes pins/news
  queries to its geofence (`ST_DWithin` filters already used by F6.2).
- **Acceptance:** switching districts moves the map + filters content; deep
  link `?district=byron-bay` lands zoomed on Byron; unknown slug falls back
  to Bondi.
- **Depends:** F7.1 (table), F3.4 (bus), F6.2 (geo RPC pattern).

---

**F8.2 — "Start a Local Loop in your area" (the growth loop, visible)**

- **What:** A prominent entry in the district switcher + footer card:
  "Run a Local Loop for your suburb — earn with your community" → form
  (name, email, suburb, existing FB group?) → writes
  `district_application` → notifies Bill → approved applications become
  `district` rows (status flow `applied→approved→live`).
- **Acceptance:** submission → row + email notification; approving (simple
  admin action in loop-onboard console) makes the district appear in the
  switcher after cache refresh.
- **Depends:** F8.1, F7.4.

---

**F8.3 — District-branded Looper dock**

- **What:** MicWave greeting + `speakResponse` intro use the active
  district ("Hey, Byron Bay Local Loop here…"); voice router's suburb
  defaults and radius center follow the active district.
- **Acceptance:** switch district → greeting text/voice changes; "find me a
  café" searches the new district's center.
- **Depends:** F8.1, F3.3.

---

### Phase 9 — Deploy & go-live (Coolify)

---

**F9.1 — Service map + DNS**

- **What:** On the existing Coolify server (`167.86.79.151`):
  | Service | Repo | Port | Domain |
  |---|---|---|---|
  | localloop-explore (exists) | localloop.pro-main | 3000 | localloop.ai |
  | looper-api (new) | looper | 8000 | api.localloop.ai |
  | typedb (new, internal) | image | 1729 | none (internal only) |
  | loop-onboard (new) | loop-onboard | 3000 | join.localloop.ai |
  | hybridcard (exists) | new-card | 3000 | hybridcard.ai |
  | looper-gateway (Cloudflare, exists) | worker | — | looper.localloop.ai |
  Fix the known `localloop.pro` Traefik default-cert/503 by re-issuing the
  cert or redirecting localloop.pro → localloop.ai at Cloudflare.
- **Acceptance:** all health endpoints green over HTTPS on their domains;
  TypeDB unreachable from the internet; `localloop.pro` no longer serves
  the default cert.
- **Depends:** F0.4, F7.1.

---

**F9.2 — Secrets, env + cron in production**

- **What:** Populate the Section 7 env table into Coolify secrets/worker
  secrets; register cron: new-card `bridge-drain` (`* * * * *`) +
  `rating-fire` (`*/5 * * * *`) (already specified in new-card CRON.md),
  looper `news_audio_worker` (`*/10 * * * *`), `brain/full_sync.py`
  (`0 3 * * *`).
- **Acceptance:** each cron shows a recent successful run in Coolify;
  secret-scan tests green; a signed test event flows in prod exactly as in
  F1.5 staging.
- **Depends:** F9.1.

---

**F9.3 — Go-live smoke checklist (run WITH Bill, one item at a time)**

1. `curl https://api.localloop.ai/health` → healthy.
2. Signed test deal → drain → approve pin → marker on localloop.ai.
3. "Hey Looper… find me a café" on the live site (Chrome, phone + laptop).
4. News test post → audio plays; Byron coords can't fetch Bondi news.
5. Test member CSV → welcome email → QR member page.
6. District switcher: Bondi ↔ Byron.
7. Ricky desktop: "any deals waiting?" (read-only cockpit).
8. Rollback notes per service (Coolify redeploy previous image; worker
   `wrangler rollback`; RLS changes have down-migrations).
- **Acceptance:** all 8 checked with screenshots archived in
  `plans/evidence/F9.3/`; ROLLBACK section filled in.
- **Depends:** everything above.

---

**F9.4 — Hot-zone flag flips (Bill-only decisions, in this order)**

1. new-card: set `LOOPER_INGEST_URL` + `LOCALLOOP_BRIDGE_URL` + secrets in
   PROD (bridge outbound goes live — Phase 11 of the card roadmap).
2. Watch one week of `bridge_events` + dead-letter counts.
3. Only then consider (card-repo governance, separate sign-offs):
   `LIVE_ALERT_FANOUT`, `SMS_LIVE`, `PAYMENTS_LIVE`, VAPID push.
- **Acceptance:** each flip logged in `.SEED/decisions.md` with date +
  reason; dead-letter count stays 0 for 7 days before the next flip.
- **Depends:** F9.3.

---

## 6. Dependency Map (what blocks what)

```
F0.1 → F0.2 → F0.4 ─┬─→ F1.1 → F1.2 ──────────┐
        F0.3 ───────┤     F1.1+F0.3 → F1.3 → F1.4 → F1.5 → F4.3
                    │                    F1.4 → F5.1, F5.2 → F5.4
                    ├─→ F2.1 → F2.2 → F2.3 → F2.5      F5.3
                    │            F2.1 → F2.4 ─────────→ F5.4, F7.5
F0.2 → F3.1 → F3.2 → F3.3        F3.2 → F3.4 → F4.2, F8.1
                    └─→ F6.1 → F6.2 → F6.3, F8.1
F0.3 → F7.1 → F7.2 → F7.3 → F7.4 → F8.2      F7.3 → F7.5, F7.6
F7.1 + F3.4 + F6.2 → F8.1 → F8.2, F8.3
F0.4 + F7.1 → F9.1 → F9.2 → F9.3 → F9.4
```

Safe parallel tracks once Phase 0 is done: **(A)** Phase 1 bridge,
**(B)** Phase 2 brain, **(C)** Phase 3 voice, **(D)** Phase 6 news,
**(E)** Phase 7 onboarding. Phases 4, 5, 8, 9 stitch them together.

---

## 7. Environment Variables (master table)

| Var | Lives in | Used by | Notes |
|---|---|---|---|
| `HYBRIDCARD_INGEST_SECRET` | looper-api (Coolify) + new-card | F1.1/F1.2 HMAC | same value both sides |
| `LOCALLOOP_BRIDGE_SECRET` | looper-gateway (wrangler secret) + new-card | F1.3 HMAC | distinct from above |
| `LOOPER_INGEST_URL` | new-card | outbox drain | `https://api.localloop.ai/api/ingest/hybridcard-deal` |
| `LOOPER_CARD_INGEST_URL` | new-card | card events | `…/api/ingest/hybridcard-card` |
| `LOCALLOOP_BRIDGE_URL` | new-card | pin events | `https://looper.localloop.ai/api/bridge` (`/pin` appended) |
| `CRON_SECRET` | new-card | drain guard | exists |
| `LOOPER_PORT` / `LOOPER_DB_URL` | looper-api | backend | defaults 8000 / sqlite |
| `TYPEDB_ENABLED` / `TYPEDB_ADDRESS` | looper-api | F2.x | `false` until F2.3 passes |
| `LOOPER_API_BASE` | looper-bot `.env.local` | F4.1 tools | default localhost:8000 |
| `OPENAI_API_KEY` / `EXA_API_KEY` | looper-bot `.env.local` | Ricky voice/search | existing |
| `MAPBOX_TOKEN`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `N8N_WEBHOOK_URL` | llx11 Coolify build env | map site | existing (ADR-0002) |
| `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | looper-gateway secrets | pin writes / F5.1 | existing |
| `ADMIN_USER_IDS` | looper-gateway var | F5.1 moderation | comma-separated UUIDs |
| `NEWS_TTS_PROVIDER` / `NEWS_TTS_API_KEY` | looper-api | F6.1 | start `openai` |
| `SUPABASE_SERVICE_KEY` (server-only) | looper-api | F6.1/F6.2 worker | never in browser |
| `INTAKE_TOKEN_<DISTRICT>` | loop-onboard | F7.2 | one per district |
| `EMAIL_PROVIDER` / `RESEND_API_KEY` (or SMTP) | loop-onboard | F7.3 | |
| `MEMBER_CODE_HMAC_SECRET` | loop-onboard | F7.3 QR codes | |

---

## 8. Risks & Open Questions

| # | Risk / question | Mitigation / owner |
|---|---|---|
| 1 | **Facebook capture legality/fragility** — VERIFIED July 2026: Groups API removed April 2024 (no app reads requests/answers, Zapier/Make dropped groups); answers vanish at approval; extension capture (Group Collector/Groupboss pattern) breaches Meta ToS §3.2.3 in principle with risk landing on the admin account; no cold DMs ever. | F7.2's 3 layers: official funnel always on; extension capture human-paced on a second admin account, Bill signs off on the trade-off; CSV fallback. F7.6 Private-Reply pilot is the only compliant DM and ships with a kill switch. Never automate approvals in v1. |
| 2 | Phase-number collision across card-repo docs (ROADMAP "Phase 20" ≠ MASTER-PLAN "Phase 20"). | This plan uses ONLY its own F-numbers; card-repo phases referenced by name + doc. |
| 3 | TypeDB driver/package naming inconsistent across specs (`typedb-driver` vs `@typedb/driver`). | Pin exact package at F2.2 implementation time from typedb.com docs; record in `.SEED/decisions.md`. |
| 4 | llx11 `index.html` is a 15k-line monolith — voice/marker edits risk regressions. | Surgical additive files (`voice-command-router.js`, `looper-map-bus.js`, `hybridcard-markers.js`), unit tests outside the monolith, evidence screenshots per feature. |
| 5 | Two voice code paths already drift (`main-map.js` vs dock). | F3.2 single router is the fix; delete duplicates same PR. |
| 6 | `localloop.pro` cert broken (Traefik default cert). | F9.1; until then all links use localloop.ai. |
| 7 | Old build's Mapbox token + style are hardcoded — do not copy them. | Port logic only; tokens via env injection (ADR-0002). |
| 8 | Supabase RLS changes on prod are dangerous. | F6.2/F7.x schema on staging first; the llx11 rule "confirmed non-production target" applies. |
| 9 | Rev-share attribution accuracy (UTM-based). | v1 = directional numbers, manual payouts; tighten later with signed referral codes (F7.3 member codes are already HMAC-signed). |
| 10 | Who approves hybridcard pins day-to-day? | Bill + district admins (F5.1 `ADMIN_USER_IDS`); Admin Assist-style auto-rules only after a month of data. |
| 11 | OpenAI Realtime / image model names in `main.cjs` may drift from current API. | Verify at F4.1 against OpenAI docs; don't refactor what works. |
| 12 | Byron Bay + future districts multiply moderation load. | F7.4 gives each district its own admin; F8.2 gates new districts behind Bill's approval. |

---

## 9. Source Document Index

| Doc | Where | What it governs here |
|---|---|---|
| `BRIDGE-CONTRACT-v1.md` | new-card/planning | F1.1–F1.5 payloads/HMAC (FROZEN) |
| `LOCALLOOP-BOT-GATEWAY-CONTRACT-v1.md` + PHASE-18/18A | new-card/planning | gateway scopes, F4.3/F5.1 write rules |
| `TYPEDB-GEO-HIERARCHY-SPEC.md` | new-card/planning | Phase 2 schema/sync/migration |
| `ARCHETYPE-SKILL-REGISTRY-SPEC.md` | new-card/planning | F2.4 archetype/skill data |
| `MASTER-DEPLOYMENT-PLAN.md`, `ROADMAP.md` | new-card/planning | card-side phase status + flags |
| `localloop-waze-bridge/*` (T1–T5) | new-card/plan | card-side halves of F1.2/F5.x |
| `SPEC/agent-collab-map-claim-hybridcard.md` | llx11 | F5.2 claim↔card flow + evidence style |
| `SPEC/pin-webhook-contract.md` | llx11 | pin payload compatibility (do not break) |
| `SPEC/business-truth-layer.md` (ADR-0006) | llx11 | F1.3/F5.1 moderation rules |
| `SPEC/looper-agent-first-architecture.md` (ADR-0005) | llx11 | gateway-mediated writes |
| `plans/MicWave.md` | llx11 | F3.x dock ids/classes/API |
| `plans/IMPLEMENTATION_PLAN.md` (llx11's own) | llx11 | Site-B rebuild PRD — SEPARATE plan, do not merge/overwrite |
| `COOLIFY_AUTO_DEPLOY_GUIDE.md` | llx11 | F9.x deploy mechanics |
| `explore-local.tsx` | golive_LocalLoop_Explore_html | F3.2 port source (logic only) |
| `FollowMe.md` (looper) | looper | repo status/history |

---

## 10. Glossary (plain English)

- **Archetype** — a business type acros all industy archtypes like (food, trades, compony, health…). Decides which
  card tools, alert tags and skills a business gets.
- **Bridge** — HybridCard automatically telling the map + LOOPER about new
  deals/cards via signed webhooks. Card = sender; we build the receivers.
- **HMAC** — a tamper-proof signature on each webhook using a shared secret.
- **Idempotent** — safe to receive the same event twice; second time changes
  nothing.
- **MicWave / Looper Dock** — the voice panel on the map site ("Hey Looper").
- **Moderation / draft pin** — card deals appear on the map only after an
  admin approves them.
- **Pin** — one record on the map (Supabase `pin` table).
- **TypeDB** — the knowledge database that stores *relationships* (what's
  near what, which skills a plumber inherits). Additive — never the boss of
  the data.
- **Rev-share** — a district admin's percentage of card signups their Local
  Loop generates.
- **Hot zone** — anything touching money, SMS, or real users; Bill signs off
  before it goes live.

---

*End of plan. Feature-file split DONE 2026-07-11 (Bill's word) — see
`plans/features/`: `01-foundation` (F0.1–F0.4), `02-bridge-receivers`
(F1.1–F1.5), `03-typedb-brain` (F2.1–F2.5), `04-voice` (F3.1–F3.4),
`05-jarvis` (F4.1–F4.3), `06-card-map-features` (F5.1–F5.4),
`07-news-audio` (F6.1–F6.3), `08-loop-onboard` (F7.1–F7.6),
`09-districts` (F8.1–F8.3), `10-deploy` (F9.1–F9.4).*


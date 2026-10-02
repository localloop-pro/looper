# .SEED/decisions.md — looper decisions log

- 2026-10-02 (issue #8, E4): public read boundary ships DARK in FastAPI
  (`backend/services/edge_boundary.py`), not in a Worker. Cache for
  search/discover/businesses (`LOOPER_READ_CACHE_TTL_S`, default 0 = off) and
  per-client read rate limit (`LOOPER_READ_RATE_LIMIT_PER_MIN`, default 0 =
  off) stay off until the owner accepts the E1 ADR (localloop.pro-main#100).
  Cache key = ranking params + TYPEDB_ENABLED + write generation; `session`/
  `intent` excluded, so cache HITs write no training_log row. Any successful
  `/api/` write clears the cache. `LOOPER_CLIENT_IP_HEADER` must stay unset
  while the sslip.io origin is directly reachable (spoofable). Any future
  edge cache must key on `Origin` too (CF ignores `Vary: Origin`). Full rules:
  `docs/EDGE-READ-BOUNDARY.md`.

- 2026-09-01: Kaspa integration v1 is a read-only organization identity
  boundary in Looper, not a wallet or authorization system. Only the configured
  ASCII `localloop.kas` and `qikflo.kas` mainnet records may resolve. Exact
  domain/asset/inscription/transaction/owner/status/verified-domain agreement
  is required; mismatch fails immediately, provider failure uses only a bounded
  validated cache, and every UI must scope the claim to the organization.
  2026-10-02 (#12): identity log lines are structured JSON with fixed keys
  (`event`, `domain`, `provider` id, mismatch `reason`/`assetCount`/bounded
  `observedOwner`). A `KNS_API_BASE_URL` override is logged only as
  scheme://host[:port]/path — userinfo, query and fragment are dropped because
  they can carry provider credentials. Raw upstream errors are never logged.

- 2026-07-10: `plans/IMPLEMENTATION_PLAN.md` created — this repo owns the
  cross-system bridge plan (looper ↔ llx11 map ↔ HybridCard). llx11 keeps its
  own separate `plans/IMPLEMENTATION_PLAN.md` (Site A/B rebuild PRD) — do not
  confuse or overwrite it.
- 2026-07-10: TypeDB is the ADDITIVE knowledge/relationship brain (geo
  hierarchy + archetype skills). SQLite (looper), Supabase (llx11) and
  MongoDB (new-card) stay the transactional sources of truth — per
  TYPEDB-GEO-HIERARCHY-SPEC.
- 2026-07-10: Voice map control is ported from the OLD build
  (`golive_LocalLoop_Explore_html/explore-local.tsx`, Web Speech API →
  keyword grammar → Mapbox flyTo/fitBounds), not rebuilt from scratch.
- 2026-07-10: Facebook group onboarding bot = a NEW separate app
  ("loop-onboard"), multi-district from day one (Bondi, Byron Bay, Rose Bay,
  Bronte, Maroubra, Bondi Junction…), with per-district admin revenue share.
- 2026-07-10: Bill approved creating SEED/AGENTS/CLAUDE scaffolding in this
  repo; hybridcard-ai "big picture" repo intentionally not read (new-card
  planning corpus is the source of truth).
- 2026-07-11: Phase 0 (F0.1–F0.4) + F1.1/F1.2 shipped on branch
  `plan/bridge-v1` (Bill approved scope, push+PR, and the feature-file
  split). Both Looper BRIDGE-CONTRACT-v1 receivers live with 39 passing
  tests. OPEN QUESTION (R2): the T2 card-payload spec in new-card omits
  `eventId`; our `/api/ingest/hybridcard-card` requires it (mirrors the
  deal payload) — confirm with the new-card side BEFORE their T2 sender
  ships, else dedupe degrades to (hybrid_card_id, updated_at).
- 2026-07-10: Facebook onboarding strategy (verified by web research):
  Groups API is DEAD (removed Apr 2024 — no app can read member requests /
  question answers / approve members; Zapier & Make dropped groups);
  membership answers are only visible while a request is PENDING (no
  export). Therefore loop-onboard captures via 3 layers — official funnel
  (reworded questions + welcome posts + join page), at-approval browser
  capture (Group Collector ~$297 lifetime / Groupboss ~$99/yr / self-built
  MV3 extension; ToS §3.2.3 risk sits on the admin account — human-paced,
  second admin account), and CSV fallback. Only compliant automated DM =
  Page Private Reply to a comment (one per commenter, 7 days,
  `pages_messaging` + `groups_feed` webhook) → F7.6 pilot with kill switch.
  Community Chats were discontinued Oct 2025 — not a channel.
- 2026-07-12: F1.3 shipped in the llx11 repo (`workers/looper-gateway`):
  `POST /api/bridge/pin` is a **dealId-keyed upsert** (one LocalLoop pin per
  HybridCard deal — deal.updated/removed PATCH in place, never twin rows) with
  the KV eventId replay ledger layered on top. Bridge pins are tier
  **`premium`** (paying businesses; the 1-month heartbeat keeps drafts alive
  through moderation — a short heartbeat would let `cleanup_expired_pins()`
  reap them unseen; tier is TTL only, never ranking). `deal.removed` ⇒
  `moderation_status='removed'` + zero heartbeat (expired); revival ⇒ back to
  `pending_review`; stale out-of-order events (older `updatedAt`) are acked
  but never applied. OPEN QUESTION (for F5.2): a content update currently
  PRESERVES a moderator's `approved` status — decide whether deal edits
  should force re-moderation. llx11 changes left uncommitted for Bill.
- 2026-07-12: F1.4 shipped in llx11: `assets/js/hybridcard-markers.js`
  (business-layer.js wrapper pattern — self-bootstraps on `localloopMap`,
  injects its own CSS; index.html got ONE script line). Renders only
  `source='hybridcard'` pins with `moderation_status IN (approved,published)`
  AND `active`, as logo markers (28/38/48/64 px by `marker_size`, fallback
  initial-letter dot) with popup + "View card →" restricted to
  `*.hybridcard.ai` (off-domain claim_url rebuilt from slug). Anti-bias: rows
  render in DB order, never sorted by discount/tier. F1.3 receiver now also
  writes `payload.lat/lng` (browser convention — see WKB gotcha). Verified
  in-browser via `LocalLoopHybridcardDemoRows` hook: approved renders at
  48px, pending/removed never render, popup fields + link correct, console
  clean. Residual for F1.5: live-Supabase seeded pin + Lighthouse >90 check.
  **Update 2026-08-02:** LocalLoop markers/Jarvis now keep bridge-supplied
  localhost path-form claim URLs (`http://localhost:3000/c/{slug}`) as-is;
  `*.hybridcard.ai`-only rewrite was the local/dev View-card failure mode.
  See Card URL contract in BRIDGE-CONTRACT-v1 + `.SEED/gotchas.md`.
- 2026-07-12: F1.5 dry run PHASE 1 executed locally (the plan's "minimal
  staging"): real new-card outbox → drainOutbox → both real receivers →
  SQLite rows + REAL Supabase draft pin (pending_review, premium, invisible
  to the public map — evidence in `plans/evidence/F1.5/`). Harness:
  `new-card/tests/integration/f15-bridge-dryrun.test.ts` (F15_DRY_RUN=1,
  phases upsert/removed, pinned dealId f150000000000000000000d1). REMAINING
  (Bill): approve the draft pin (prod write — hot zone, permission gate
  correctly blocked the agent), run phase `removed`, delete/retire the TEST
  pin, then the true staging deploy (worker secrets/KV, Coolify envs, cron).
  F1.5 box stays UNTICKED until those pass.
- 2026-07-11: The desktop bot is named **Looper** (Bill's word) — "Ricky" and
  the ported "Riley/rileyjarvis" persona are retired. Full rename in
  looper-bot (UI strings, instructions, window.looper bridge, package name
  looper-bot, LooperFace component); local data auto-migrates
  ricky-db.json → looper-db.json on first launch. Voice dock on the map was
  already "Hey Looper" — now consistent everywhere.
- 2026-07-12: Jarvis map layer (Bill's ask: "make Looper a Jarvis that controls
  my map") built as SELF-CONTAINED embeddables in `web/jarvis/` of THIS repo —
  the llx11 repo was not writable from the build session, and one-script-tag
  embeds respect ADR-0003 ("index.html is sacred") anyway. Four framework-free
  modules: `voice-command-router.js` (F3.2 grammar port from explore-local.tsx,
  46 node unit tests, stop-substring + stale-radius + accent bugs FIXED),
  `looper-map-bus.js` (F3.4 control surface: setCategory/flyTo/fitCategory/
  zoom/reset/showBusiness/showResults), `looper-face.js` (the LooperFace.tsx
  face as a vanilla widget — same CSS-var mouth, blink/pupil animations),
  `looper-jarvis.js` (orchestrator: Web Speech in, chunked TTS out with
  barge-in cancel, persona, /api/search answers, F4.2 deep-link parsing
  ?cat=&q=&fly=). Demo at `GET /demo` (MapLibre + OSM raster, zero keys —
  production keeps Mapbox per ADR-0002). llx11 integration = 4 script tags +
  LooperJarvis.init (snippet in README); F3.2/F3.4 acceptance boxes stay
  unticked until wired into llx11 itself.
- 2026-07-12: Backend search is now accent-folded via a registered SQLite
  function `fold_accents` (models.py) — "cafe" finds "café" (the F3.x gotcha).
  `/api/search` results gained `website` + `card_url` (HybridCard public card
  link — surfaced as "View card →", NEVER a ranking input; test asserts a
  carded business gains no rank). New read-only `GET /api/ingest/status`
  (F4.3 cockpit read path). `web/` is now mounted by FastAPI at `/web`.
- 2026-08-02: `card_url` is a pure pass-through of stored
  `Deal.public_card_url` / bridge `Business.website`. Removed the
  `.hybridcard.ai` host gate so local HybridCard path URLs
  (`http://localhost:3000/c/{slug}`) survive search + discover. Shared helper:
  `resolve_card_url()` in `backend/routes/search.py`. No slug rebuild in looper;
  Jarvis already uses `r.card_url` only.
- 2026-07-12: F4.1/F4.2 (looper-bot): Looper gained localloop_search /
  localloop_businesses / localloop_open_map (deep link via shell.openExternal)
  / localloop_bridge_status tools + LocalLoop persona block in
  LOOPER_INSTRUCTIONS (desktop face of LOOPER, anti-bias, must-use-tools,
  aggregate-counts privacy). Env: LOOPER_API_BASE, LOCALLOOP_MAP_URL.
- 2026-07-12: Build-session gap: this cloud env blocks PyPI + npm, so
  `pytest` and `npm run typecheck && npm run build` could NOT run here.
  Verified instead: py_compile all touched backend files, stdlib-sqlite proof
  of fold_accents, node --check all JS, 46/46 router unit tests, and a full
  Playwright headless flow (web/tests/jarvis-smoke.playwright.js — search,
  suburb, zoom, reset, deep links, card links, zero console errors). Bill (or
  next agent with network): run both quality gates before merging.
- 2026-07-12 (slice 2, same branch): F2.3 fallback half shipped —
  `GET /api/discover` returns the frozen graph-era response shape with
  `engine:"fallback"` (SQLite haversine; suburb seed table in
  routes/discover.py MIRRORS web/jarvis/voice-command-router.js SUBURBS —
  keep in sync until TypeDB F2.1 owns geography). F2.5 core shipped:
  /api/search + /api/discover write training_log via services/telemetry.py
  (intent + anonymous session id; emails + AU mobiles regex-scrubbed;
  telemetry failures never break the request). Jarvis web dock gained a
  hands-free "Hey Looper" wake mode (open mic acts only on wake-word
  utterances; while Looper speaks, only a stop command interrupts — guards
  against the mic hearing Looper's own TTS and cancelling itself). Desktop
  Looper gained localloop_discover. Same verification regime as slice 1
  (py_compile, node --check, 46 router tests, Playwright smoke — pytest and
  npm gates still owed on a networked machine).
- 2026-07-21: Online bridge go-live path shipped without Coolify UI access.
  `api.localloop.ai` is a Cloudflare Worker (`workers/looper-api-proxy`) that
  reverse-proxies to a cloudflared ORIGIN (local FastAPI :8001) until Coolify
  login is reset and a durable Docker origin is attached. Gateway
  `looper.localloop.ai` redeployed with BRIDGE_EVENTS_KV +
  LOCALLOOP_BRIDGE_SECRET. Evidence: `plans/evidence/F9.1/`.
- 2026-08-11: F2.1 + F2.2 + F2.3 (graph engine) + F6.1 code-complete on
  branch `claude/looper-jarvis-map-app-vskorv`. TypeDB schemas
  `brain/schema/001_geo.tql` (geo hierarchy: world→country→state→city→suburb
  →locality; `located_in`; `nearby` with `distance_km`) and
  `brain/schema/002_business.tql` (business_entity with hybrid_card_id,
  is_active, lat/lng; `serves_area`, `franchise_of`, `subsidiary_of`)
  match TYPEDB-GEO-HIERARCHY-SPEC. `brain/migrate.py` tracks applied schemas
  in `brain/.applied_migrations` (idempotent). `brain/seed_geo.py` inserts
  21 suburbs (Eastern Suburbs + Byron Bay) + pre-computes `nearby` pairs
  ≤ 10 km. `brain/sync.py` upserts business_entity + located_in (nearest
  suburb haversine from suburbs.csv); NEVER raises. `brain/full_sync.py`
  nightly CLI. `routes/ingest.py` fires BackgroundTask `_brain_sync()` after
  every bridge ingest (F2.2). `_graph_discover()` in `routes/discover.py`
  now fully implemented (F2.3): TypeDB DATA session → get all active
  business_entities + suburb name → Python haversine suburb filter →
  SQLite hydration + category filter → anti-bias ranking → engine:"graph".
  Falls back to SQLite on ANY TypeDB error. F6.1: `tools/news_audio_worker.py`
  reads `news_post.audio_url IS NULL`, strips markup, calls OpenAI TTS tts-1,
  uploads to Supabase Storage `news-audio` bucket, sets `audio_url`. Env:
  NEWS_TTS_PROVIDER/NEWS_TTS_API_KEY/NEWS_AUDIO_BUCKET/NEWS_AUDIO_VOICE/
  NEWS_MAX_CHARS/NEWS_AUDIO_BATCH. `requirements-brain.txt` added:
  typedb-driver>=2.28.0 (PIN exact version on first install — run
  `pip index versions typedb-driver`), supabase>=2.0.0. Acceptance pending
  Bill deploying TypeDB in Coolify + creating `news-audio` bucket.
- 2026-07-28: "Brain offline" on live map diagnosed: CORS (backend allowlist
  lacked localloop.ai — fixed, committed 7c6753b on main, Coolify looper-api
  redeployed via API, verified: `access-control-allow-origin:
  https://localloop.ai` now returned) + missing `LOOPER_API_URL` env on the
  llx11 Coolify app (site's looperApi still localhost:8000). Bill to set
  `LOOPER_API_URL=https://api.localloop.ai` on app zl9s2tebckbu9zgzkdy2en4t
  and redeploy (agent's env-write was permission-blocked).
- 2026-08-12: TypeDB local acceptance completed against pinned Core 2.29.1
  and `typedb-driver==2.28.4`: idempotent migration + 21-suburb/378-nearby
  seed; Bondi query includes Bronte/Bondi Junction; signed bridge ingest
  creates business + `located_in`; TypeDB-down ingest remains 200; full sync
  backfills 20/20; graph/fallback parity is exact (20 ordered results). Added
  opt-in real-service integration coverage plus blank-env/zero-coordinate
  regressions. Empty `TYPEDB_ADDRESS`/`TYPEDB_DB` now mean safe defaults —
  this fixes the observed driver `invalid format` failure and prevents silent
  graph fallback in Coolify. Production boxes remain gated on Bill deploying
  the internal-only TypeDB service/env/nightly task. F6.1 gained four isolated
  worker tests; real bucket/TTS/cron/player acceptance remains owner-gated.
- 2026-08-12: LocalLoop confirmed llx11 already embeds and binds the Jarvis
  router/bus/face/orchestrator/boot stack and deep links. F3/F4 are no longer
  blocked on wiring; remaining evidence is two direct-contract tests
  (`looper-map-bus.js`, `applyDeepLinks()`) plus Bill's real mic/browser and
  desktop voice acceptance. F4.3 pending-pin artifact/audit remains partial.
- 2026-08-12: LocalLoop PR #75 subsequently merged to llx11 main as `158299a`;
  install/secret scan, unit/integration, Playwright E2E, and `ci-required`
  remote checks were all green, and tracking issue #77 auto-closed. This
  closes the cross-repo integration/merge gate, not the two direct-contract
  evidence tests or Bill's live mic/deep-link smoke. Beauty & Wellness #76
  remains explicitly paused/backlog; Looper starts no pilot implementation.
- 2026-08-12 wrap-up: corrected F4 status before compaction. F4.1 still lacks
  planned desktop `localloop_pins` and `localloop_gateway_health` tools;
  archetype-skills waits on F2.4. Public gateway health is live (HTTP 200), but
  no implementation was started after the coordinator's wrap-up notice. F4.3
  cannot finish inside Looper: llx11 `158299a` exposes no supported read-only
  machine endpoint for pending HybridCard pins and defines no bot auth,
  response/pagination schema, or read-audit semantics. The existing admin
  browser direct-Supabase query is not a machine contract and must not be
  copied. Exact restart state is in `plans/COMPLETION_STATUS.md`.
- 2026-08-12: Coordinator sanctioned the F4.3 Looper client against LocalLoop
  SPEC-055. Added Electron-main-only `localloop_pending_pins` bearer client and
  `localloop_gateway_health`. The pending client fixes HybridCard/pending filters,
  bounds page/limit, validates exact pagination + the 21-field allowlist,
  strips unsafe links/unrecognized fields, rejects redirects and insecure
  token destinations, escapes untrusted table text, restricts card links to
  HybridCard/loopback hosts, validates each pin's fixed source/status, uses a
  10s timeout, and withholds all data on malformed, auth, select, backend, or
  audit failures. Fifteen Node tests + desktop
  typecheck/build + live public health passed. LocalLoop branch `cd4c751`
  (core `71c3052`, hardening `af31947`) is reported green but **not merged or
  live**; no production token/acceptance claim until final merge SHA, owner
  activation, a live audited 200, and Bill voice acceptance.
- 2026-08-12: SPEC-055 provider then merged through LocalLoop PR #80 to main
  at `d77ccf8659638f71ee39f813691ecd597d1aa0d3` (feature PR #79 squash
  `7043938`); Install+Secret Scan+Lint, Unit/Integration, Playwright E2E, and
  `ci-required` passed, and issue #78 closed. Merge resolves the contract/code
  blocker only. Production remains owner-gated: apply
  `db/migrations/looper_gateway_audit_log.sql`, provision the identical random
  32+ byte `LOOPER_BOT_READ_TOKEN` in Worker + Looper, deploy, and correlate a
  live 200 with `pin_pending_list_read` before Bill's voice acceptance.
- 2026-08-23: Voice-quality overhaul on `claude/voice-self-improve-kvdr04`
  (Bill's ask: "get the voice working as well as possible"). Desktop
  (looper-bot): session now enables input transcription
  (gpt-4o-mini-transcribe + LocalLoop-name prompt — Bill's spoken turns
  finally appear in the Live Log), far_field noise reduction, and
  env-overridable model/voice/eagerness/speed (defaults unchanged per the
  model-name gotcha); realtime.ts gained auto-reconnect (pc/dc death,
  60-min session_expired, mic unplug — fresh secret each dial-in, context
  resets), low-latency tool dispatch on response.output_item.done with a
  handledCallIds dedupe, try/finally + per-call error outputs so a failed
  tool can't wedge the conversation, response.cancel before typed prompts,
  cancelled-response "(interrupted)" transcript labeling, and
  analyser-driven "speaking" mood (audio-delta events never fire over
  WebRTC — that handler was dead code). Web Jarvis: wake vocabulary moved
  into the router as the single source of truth (WAKE_RE/WAKE_STRICT_RE,
  ASR mishears loopa/luper/luber/"loop a"; 'cooper' and bare 'loop'
  deliberately rejected), wake-prefixed barge-in while Looper speaks
  (greeting reworded so TTS can't self-wake), hands-free no longer dies in
  a quiet room ("no-speech" is benign in wake mode) and re-arms after
  screen-lock/tab-switch drops, quality-ranked TTS voice picker
  (Natural/Premium/Google > compact/eSpeak within the same language tier),
  and a settleUi() helper so the status pill/face never stick on "On it."
  or show idle with a hot mic. Router tests 165→173; all gates green
  (typecheck/build, 15 gateway tests, backend 80 pass/1 skip, Playwright
  smoke). Bill's live-mic acceptance still owed as before.
- 2026-08-12: F4.3 Looper client is code-complete and checkpointed in
  coordinator commits `854e1e7` (integration) and `7a91cb5` (gateway module,
  15 tests, evidence). LocalLoop confirmed no contract mismatch against merged
  SPEC-055. Remaining work is owner-gated only: Bill applies the audit
  migration, provisions the identical token in Worker + Looper, deploys the
  Worker, proves a live audited HTTP 200, and completes voice acceptance.
  Keep the F4.3 checkbox open until those production gates pass.

### F4.3 owner gates: 1–2 + deploy + HTTP-layer proof executed; gate 3 partial (2026-08-22)

- Owner (Bill) directed the coordinator to run the SPEC-055 owner-gate chain.
  Executed: the audit migration, shared-token provisioning, Worker deploy, and
  a live audited 200 at the HTTP layer (direct endpoint probe). Gate 3's direct
  `localloop_pending_pins` Electron-tool invocation is NOT done (evidence README
  marks item 3 `[~]`), so the production-client proof and voice acceptance
  (gate 4) remain outstanding — do not treat F4.3 as fully accepted.
  These steps ARE hot-zone work (a production migration, an auth-secret
  provisioning, and a Worker deployment) — executed here specifically because
  the owner authorized this chain. The scope boundary was: execute the F4.3
  activation hot-zone steps only, and do NOT touch the separately-gated
  news-audio/TTS-cost approval or the go-live feature-flag flips
  (`LOOPER_INGEST_URL`/`LOCALLOOP_BRIDGE_URL`/`LIVE_ALERT_FANOUT`/`SMS_LIVE`/
  `PAYMENTS_LIVE`), nor the voice acceptance — those remain untouched.
- Applied `looper_gateway_audit_log.sql` to production Supabase (RLS enforced),
  provisioned one fresh 32-byte `LOOPER_BOT_READ_TOKEN` in the Worker secret
  store and `looper-bot/.env.local` (0600), deployed `localloop-looper-gateway`
  from `origin/main` (Cloudflare version `0fb82412`), and proved the live
  audited 200 (+401/+422 negatives; audit row `12957da6`, 16:38:20Z).
- Evidence: `plans/evidence/F4.3-pending-pins/README.md` (live smoke record).
- F4.3 now blocks ONLY on voice acceptance (restart looper-bot first so
  Electron loads the token). TTS-cost and hot-zone flags remain untouched and
  separately gated.

### Worker sets X-Request-ID from cf-ray (looper#17, 2026-10-02)

- `workers/looper-api-proxy` now keeps a safe inbound `X-Request-ID`
  (8–128 chars of `[A-Za-z0-9._:-]`, at least one letter — the E6 rule) and
  otherwise sets it from the opaque `cf-ray`, falling back to
  `crypto.randomUUID()` when there is no ray (local `wrangler dev`). Unsafe ids
  (phone-shaped digits, emails, `Bearer …`) are replaced, never forwarded, so
  Cloudflare logs and Looper trace records share one PII-free key. The
  Worker's own 500/502 replies echo the id.
- Code only. It is NOT deployed: deploying the Worker is an owner/devops step
  in an approved change window (`api.localloop.ai` route). Tests:
  `node workers/looper-api-proxy/test/index.test.mjs`.
- The other #17 items stay open and blocked outside this repo: E1 thresholds
  (localloop.pro-main#100), map/gateway ids (#101/#102), HybridCard outbox
  logs (hybridcard-v2#62), a named non-prod staging target for the cross-repo
  browser E2E, and the owner's production sign-off.

### E6 release gate — Looper slice: correlation, SLO report, non-prod checks (2026-10-02, looper#9)

- One correlation convention: `X-Request-ID` on HTTP hops (opaque 8–128
  `[A-Za-z0-9._:-]` with at least one letter, else replaced by uuid4 hex,
  so a dictated phone number can never become a trace key); bridge events
  join on the existing payload `eventId` — no header or payload change, the
  contract stays frozen.
- `backend/services/correlation.py` is the outermost ASGI layer. It writes
  the canonical id back into the scope, so the merged PR #16 read boundary
  echoes the same id. It emits allowlisted JSON lines (`kind: http` / `kind: bridge`) to
  stderr: route template only, never query/IP/UA/auth/body/business data.
  `LOOPER_TRACE_LOG=off` is the kill switch. It writes no rows.
- Bridge delivery age = receive time − payload `updated_at`, because
  `X-HC-Timestamp` is re-signed on every retry.
- `tools/slo_report.py` (report + compare) is the release gate.
  `tools/slo_thresholds.json` is PROVISIONAL until the E1 ADR
  (localloop.pro-main#100). Too few samples = fail.
- `tools/e6_nonprod_check.py` refuses localloop/hybridcard/sslip hosts and
  any non-loopback host without `--non-prod-host`.
- Runbook: `docs/E6-RELEASE-GATE.md`. The cross-repo staging E2E and the
  owner production sign-off remain open by design.
- uvicorn's default access log was ON in production (`Dockerfile` CMD). It
  logged the client IP and the raw query string, and voice queries can carry
  dictated emails/mobiles. `main.py` now passes `access_log=False` (local
  runs). The Dockerfile `--no-access-log` is a deploy change, so it waits for
  the owner's OK on looper#9; until then the release gate marks it ⚠️ and a
  strict-xfail test tracks it. Security reviews must say what is still open,
  never ✅ a gap outside the code they changed.

### Provisional SLO thresholds can't sign off production (2026-10-02, looper#20)

- Every item in looper#20 is blocked outside this repo or needs the owner
  (ADR localloop.pro-main#100 still Proposed; #101/#102 and hybridcard-v2#62
  open; no staging target named; deploy and sign-off are owner-only). Agents
  don't invent threshold numbers or a staging host.
- What could be done in this repo: `slo_report.py` validates the thresholds file
  (exit 2 when invalid) and `--require-final` fails while `provisional` is true. A
  final file must name its `adr`. The ADR swap is now a one-file edit plus
  one test assert, and a green run on placeholder numbers can't be
  taken as production approval.


### Public writes behind a kill switch, profile reads deleted (2026-10-02, looper#27)

- BLIND-SPOTS §3.6 / step 7. `POST /api/reviews`, `/api/onboard` and `/api/pins`
  answer 403 `{"detail": "public writes are disabled"}` unless
  `LOOPER_PUBLIC_WRITES` is exactly `true` (`services/write_guard.py`).
  Attached per route decorator, never on the routers: those routers also hold
  the public `GET /api/reviews/{id}`, `GET /api/pins`, `GET /api/tourist-info`.
  It is a dependency so an empty body gets 403, not 422.
- `GET /api/users/{id}` and `GET /api/code/{code}` are deleted, not flagged: no
  caller exists (Telegram bot never launched) and the write flag must never be
  able to reopen a join-code leak. If a feature needs them back, they return
  behind their own bearer guard (`require_profile_reader`).
- `verified_visit` is no longer in `SubmitReviewRequest`; the server always
  stores `False` for a direct submission (extra body fields are ignored).
  `seed.py` still writes `True` straight to the DB — throwaway DBs only.
- `POST /api/onboard` with an already-registered mobile returns 409
  `{"detail": "could not complete sign-up"}` with no id, name or join code.
  The 409 still tells a caller the number exists (enumeration); acceptable
  while writes are off, revisit with OTP before flipping the flag.

### Search synonym + compound-word table (2026-10-02, looper#29)

- `backend/services/query_terms.py` expands each query word before matching
  (BLIND-SPOTS §3.16 half b, owner-approved): hairdresser/hairdressers/"hair
  dresser" → hair, salon; salon → hair, hairdresser; barber → hair, barber;
  cafe/café ↔ coffee; plus a few seed-category words (gp, chemist, gym,
  sparky, dental, vets…).
- The user's own word is always kept and still matches as a substring
  (pre-#29 behaviour). Added alternatives must start a word, so "hair" never
  matches "Chair Hire". No blanket "query word contains name word" rule:
  "carpet cleaner" never matches "Car Wash".
- Relevance scores each query word once (its best alternative), so an
  expanded word can't outweigh an unexpanded one. Sort key unchanged:
  relevance, review count, distance. A test ingests a 90%/rank_boost deal
  with a card URL over the signed bridge and proves the order doesn't move.
- `web/jarvis/voice-command-router.js` sends only the user's own hair noun
  (barber words → "barber", hairdresser words → "hairdresser", salon words →
  "salon", bare "hair" → "hair"), all before the health bucket, and lets the
  backend table expand it. Padding the term with a bare "hair" made spoken
  "hairdresser" reach "Chair Hire" (PR #34 QA round 1). Change both files together.
- The parts of a two-word compound ("hair dresser"), and a word that another
  word in the same query already adds ("barber hair"), match only at the start
  of a word. Typed bare "hair" still matches as a substring, as on main.
- Code only. The Coolify redeploy of looper-api and the Aesthete category
  change on hybridcard.ai stay with the owner.

### Identity reads are outside the per-IP read limit (2026-10-02, looper#40)

- `services/edge_boundary.py` `RATE_LIMIT_EXEMPT_PREFIXES = ("/api/identity/",)`.
  HybridCard's badge proxy calls `/api/identity/domains/{domain}` server-side,
  one IP for all hybridcard.ai visitors; a per-IP bucket would hide the badge
  for everyone once `LOOPER_READ_RATE_LIMIT_PER_MIN` is turned on.
- Looper adapts (receivers adapt); it does not rely on HybridCard changing
  `cache: 'no-store'` to `revalidate: 60`, though that would still help.
- Safe because the verifier only resolves the fixed `.kas` allowlist from its
  own TTL cache with single-flight and failure back-off. If identity ever
  accepts arbitrary domains, revisit: give it its own (higher) limit instead.
- Exempt is a strict prefix with trailing slash: `/api/identityx` stays limited.

### Jarvis router drift check; the map re-sync is the map repo's job (2026-10-02, looper#39)

- The live map ships its own copies of `web/jarvis/*.js`, and they had drifted.
  Its router lacked surry hills/redfern/alexandria and the wake mishears
  (`loopa`, `luper`, …), and its dock hard-codes `WAKE_RE`, so it has no strict
  barge-in. The fix belongs in localloop.pro-main (filed as
  localloop.pro-main#334). Agents here never edit that repo.
- Looper's side: `tools/jarvis-sync-check.js` (zero deps, read-only). It
  checks that `SUBURBS` equals `SUBURB_COORDS` in `routes/discover.py` (keys
  and lat/lng), that `WAKE_RE`/`WAKE_STRICT_RE` are exported, that the map
  dock reads `Router.WAKE_*`, and that a fixed phrase list routes the same as
  Looper. With `--map <dir>` it checks the map copy too. Pytest runs the
  Looper-only half, so adding a suburb to one table and not the other now
  fails the suite.
- The check compares behaviour (route output for the probe phrases), not file
  text. Map-only changes (card-link canonicalizer, SPEC-067 panel) are
  allowed to differ. Which repo owns these files stays ADR
  localloop.pro-main#100's call.

### GitHub Actions CI (2026-10-02, looper#32)

- `.github/workflows/ci.yml` runs on PRs to main and pushes to main with
  `permissions: contents: read`, no repo secrets and no deploy steps. Jobs:
  backend (Python 3.12, pytest), web (Node 20, voice router + Jarvis drift tests), worker
  (looper-api-proxy tests), looper-bot (npm ci, typecheck, build, test; no
  Electron binary download, no packaging, no keys), gitleaks, and a final `ci`
  job that needs all of them.
- gitleaks matches hybridcard-v2's setup (full-history checkout, auto
  `GITHUB_TOKEN`, job-level `pull-requests: read`) but on `gitleaks-action@v3`,
  because v2's Node 20 runtime is gone from hosted runners since 2026-09-16.
  The repo is owned by a personal account, so no `GITLEAKS_LICENSE` is needed.
- Making `ci` a required status check on `main` is the owner's step.

### Search card link: `card_url` only, no `slug` (2026-10-02, looper#38)

- `/api/search` results carry `card_url` as the only card link. It is the
  sender's `public_card_url`, returned as sent for any host (tunnel hosts
  too), never rebuilt from a slug, never a ranking input.
- No `slug` field in `SearchResult`. Adding it needs a new `businesses`
  column filled from the card payload's `slug`. That is a schema change to
  live data (hot zone) with no owner OK, so the consumer adapts instead:
  the map's Jarvis dock should drop its `r.slug` read
  (localloop-pro/localloop.pro-main#333).
- Pinned by `backend/tests/test_search_card_link_contract.py`: no `slug`
  even when the card event sent one, tunnel URLs returned as sent, and a
  carded 90%/rank_boost deal still ranks below a reviewed business.
- Revisit only if the owner approves the column. Then add it as nullable,
  fill it from card events going forward, and never derive `card_url` from it.

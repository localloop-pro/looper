# Vision

LOOPER is LocalLoop's community connection agent: a voice and text "Jarvis"
that helps a person in one suburb find real local businesses and services,
answered only from verifiable community evidence (reviews, recency,
proximity) and never from sponsorship. It is the bridge brain between three
shipped systems: the live LocalLoop Explore map (localloop.ai), HybridCard
digital business cards (the HMAC bridge sender), and the Bondi / Byron Bay
Local Loop Facebook communities. Owner: Bill, QikFlo Pty Ltd. Bill is a basic
coder, so everything here must stay runnable and verifiable by a beginner with
copy-paste commands.

The factory scores every piece of work against this file. The master plan is
`plans/IMPLEMENTATION_PLAN.md`; the weekly truth is `STATUS.md`; the rules are
`AGENTS.md`, `SEED.md`, `.SEED/decisions/` and `.SEED/gotchas.md`.

## Goals

In order. The first gate decides what is built after it; do not skip ahead.

- **Prove "one suburb, one loop" with real strangers.** Ten strangers say
  "Hey Looper, find me a hairdresser" on localloop.ai, hear at least two
  options, tap "View card", and land on a working HybridCard page. That count
  is the number that unfreezes everything else (`plans/BLIND-SPOTS-2026-09-08.md`
  §5 and §6). Work that moves `scripts/loop_check.py` from `NOT READY` to
  `READY` scores highest.
- **Make production truthful and measurable.** `/health` reports the deployed
  commit and it matches `main`; Bill's Monday check (`STATUS.md`) runs in five
  minutes; `backend/scripts/weekly_numbers.py` reports queries, zero-result
  rate and coverage gaps from a backup copy. `STATUS.md` says "unverified
  (owner probe needed)" rather than guessing.
- **Close the open doors before public traffic.** Public writes stay 403 until
  a verified path exists; the origin lock to the Cloudflare Worker is merged,
  deployed and verified before any client-IP header is trusted; forwarded-header
  trust is narrowed; the read cache and rate limit stay dark until the E1 ADR is
  accepted (`docs/EDGE-READ-BOUNDARY.md`, `docs/E6-RELEASE-GATE.md`).
- **Only real businesses, from honest sources.** Never seed test data into
  production. Grow the brain through the owner-verified CSV import
  (`backend/scripts/import_businesses.py`) and, after the loop is proven, a
  nightly read of the map's moderated Business Truth Layer. Always return two
  or more truthful options where the data allows it.
- **Keep the HybridCard bridge boring.** Both BRIDGE-CONTRACT-v1 receivers stay
  idempotent and replay-tolerant; card URLs come through as sent; dead-letter
  count stays at zero for seven days before Bill flips any hot-zone flag
  (`plans/features/10-deploy.md` F9.4).
- **Keep the Jarvis fast and honest.** Time-to-first-speech stays within the
  baseline in `docs/SPEED-BASELINE.md`; typed fallback always works when the
  microphone or Web Speech is unavailable; the public API front door
  (`backend/public_surface.py`) is verified on Coolify before
  `LOOPER_FRONTDOOR_LIVE` is turned on.
- **Then, and only then,** resume `plans/features/` in order (03 TypeDB brain,
  04 voice, 05 Jarvis, 06 card-map features, 07 news audio), ticking a
  checklist box only when that feature's Acceptance passes.

## Target users

- **People in the suburb (Bondi first, Byron Bay next).** Residents and
  visitors asking the map, the embeddable widget or the desktop companion
  "find me a café / hairdresser near me". They need two or more truthful
  options, distance, genuine review evidence, a working card link, an answer in
  a couple of seconds, and a typed path when voice is unavailable.
- **Local business owners with a HybridCard.** They need their card and deals
  to appear on the map after moderation, with the deal sizing the marker and
  never the rank, and their public card URL preserved exactly as HybridCard
  built it.
- **Bill, the owner and operator.** Runs the Monday check, deploys on Coolify,
  approves every hot zone. Needs copy-paste run and verify steps, a truthful
  `STATUS.md`, a rollback line per change, and no surprises in production.
- **Facebook community members (156K Bondi, 6K Byron Bay).** The distribution
  asset. Today they are reached by posts and the free funnel only; no code
  touches them until the loop is proven.
- **Integrators in the sister repos and the coding agents.** LocalLoop Explore
  (`llx11`) embeds `web/jarvis/*` and `web/looper-widget.js` by script tag;
  HybridCard sends frozen bridge events. They need stable response shapes,
  frozen contracts, and `.SEED/` decisions they can trust.

## Principles

- Small, well-tested changes
- Keep the public API stable
- **Anti-bias is non-negotiable.** Rank by reviews, recency and proximity
  only. `rank_boost` is always `false`. Never declare a "best" business. Always
  show multiple options. Discounts size markers, never rankings. No paid
  placement, ever.
- **Public-safe by construction.** No names, mobiles, emails, VIP identities
  or keys leave this system in bridge payloads, telemetry, logs or evidence.
  Aggregate counts only. Scrub dictated contact details before storage.
- **Frozen contracts; receivers adapt.** BRIDGE-CONTRACT-v1 payload shapes,
  the HMAC scheme and the Card URL contract are owned by the sender. This repo
  never rewrites, rebuilds or gates on a card URL, and `deal.removed`
  deactivates, never deletes.
- **Dark by default.** New behaviour ships behind an env flag that defaults
  off (`LOOPER_PUBLIC_WRITES`, `LOOPER_ORIGIN_KEY`, `LOOPER_READ_CACHE_TTL_S`,
  `LOOPER_FRONTDOOR_LIVE`, `TYPEDB_ENABLED`). Bill flips flags; agents never do.
- **Agents never touch production.** No production probes, deploys, DB writes
  or secret handling by agents. Bots write only through audited gateway
  endpoints with idempotency keys and approval gates. Owner runbooks are
  dry-run for agents.
- **Truthful status over optimistic status.** Historical evidence is labelled
  historical; anything not probed by the owner is "unverified". Never invent a
  parallel tracker; use `STATUS.md` and the master plan.
- **Beginner-runnable.** Every change ends with copy-paste run and verify steps
  and a one-line rollback that Bill can follow on his Mac.
- **Stay in scope.** Do what the task needs; no unrequested features, files,
  refactors or docs. Suggestions go at the end of the report.
- **One file per decision or lesson, per PR.** New entries go in
  `.SEED/decisions/` or `docs/learnings/` as `<issue>-<short-slug>.md`; never
  append to `.SEED/decisions.md` or `docs/LEARNINGS.md`.
- **Fix the code, never the workflow.** A red CI run is fixed in the code. No
  secrets, deploy steps or write scopes are added to CI; the secret scan is
  never skipped or allowlisted around.
- **Trust the file tree, not the README.** Stale docs are corrected, not
  followed.

## Out of scope

- Telegram bot, Hermes profile and `looper` CLI wrapper, HuggingFace
  fine-tuning, TypeDB Cloud or TypeDB in production, DB2 telemetry, device
  sync, wallet passes, Discourse SSO, Bubble, any new agent framework,
  governance rule or planning document (`STATUS.md` "Not now").
- Kaspa KRC-20 token, wallets, Deal Passes, signing or authorization via
  Kaspa. The read-only organization identity check (`localloop.kas`,
  `qikflo.kas`) is the whole Kaspa scope.
- Districts (`plans/features/09`), the loop-onboard app (`08`), bookings
  phases 4 to 10, and any multi-suburb expansion until the loop success rule
  has a number next to it.
- A receiver for HybridCard partnership events. Option A was chosen: the
  sender stopped, the 422 guard stays, dead letters are never replayed.
- Seeding, importing or fabricating businesses, reviews, ratings or social
  proof in production. Any ranking signal other than reviews, recency and
  proximity. "Best of" lists, sponsored results, paid placement.
- Rewriting or regenerating `llx11` `index.html`; changing the HybridCard
  sender contracts from this repo; rebuilding card URLs from slugs in Looper.
- Direct production database writes, production probes, deploys, DNS or
  Cloudflare changes, secret creation or rotation performed by agents.
- Sending SMS, email, Facebook messages or any message to a real person.
- Weakening quality gates: removing or skipping the gitleaks job, adding
  `continue-on-error`, adding secret-scan allowlist entries, lowering test
  counts to make a run green.
- New top-level dependencies without a written justification; growing the lean
  backend requirements (`.SEED/decisions/55-lean-backend-requirements.md`).
- Unrequested refactors, renames, new abstractions, or docs beyond what the
  task requires.

## Quality bar

- Every behaviour change comes with tests
- CI is green before merge
- "Green" means the single required `ci` check in
  `.github/workflows/ci.yml`: backend pytest, web node tests, Jarvis
  Playwright smoke, Worker tests, looper-bot typecheck + build + tests,
  production Docker image smoke, dependency audit and gitleaks. Run the
  `AGENTS.md` quality-gate commands locally before opening the PR.
- Public response schemas, status codes (403 on locked writes, 404 unknown
  business, 422 bad coordinates) and the root JSON key order stay unchanged
  unless the PR says so and the sister repos are told via
  `docs/CROSS-REPO-CONTRACTS.md`.
- Every new flag defaults off, is documented in `.env.example`, and the PR
  carries a one-line rollback.
- No PII, real secret values or production data in code, tests, fixtures,
  evidence or runbooks. `backend/tests/test_secret_rotation.py` stays green;
  a leaked value is rotated, never just edited out.
- Changes to search, discover or businesses read paths keep the batched
  review-stats pattern and are benchmarked with `tools/bench_read_paths.py`
  or `tools/bench_search.py` when ordering or query shape changes.
- Each PR adds exactly one decision or lesson file where a decision or lesson
  was made, and includes copy-paste run and verify steps a beginner can follow.
- A PR never claims production state. Production verification is Bill's
  Monday check; the PR records what was verified locally and in CI.

## Protected areas

Paths (globs in backticks) and topics that always need a human. The factory
never merges changes that touch them; they go to your inbox.

- `**/auth/**`
- `**/migrations/**`
- `.github/workflows/**`
- `.github/scripts/**`
- `LICENSE`
- `looper-bot/LICENSE`
- `backend/models.py` (in-code SQLite schema and column migrations)
- `brain/migrate.py`, `brain/schema/**`
- `backend/routes/ingest.py`, `backend/services/bridge_hmac.py` (frozen
  HybridCard contract and HMAC verification)
- `backend/services/write_guard.py`, `backend/services/origin_guard.py`,
  `backend/services/edge_boundary.py`, `backend/services/cors_policy.py`
  (security gates and allowlists)
- `backend/routes/identity.py`, `backend/services/kaspa_identity.py`
  (organization identity)
- `backend/services/pii.py`, `backend/services/telemetry.py`, `training/**`
  (customer data and what is stored about people)
- `backend/seed.py`, `backend/scripts/**` (import, backup and weekly numbers
  touch real or production-shaped data)
- `backend/services/facebook_pipeline.py` (real members' posts)
- `backend/Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`,
  `workers/**`, `plans/scripts/**` (deploy, Worker and environment)
- `looper-bot/electron/**` (API key handling, computer control, tool
  confirmation policy, window hardening)
- `tools/news_audio_worker.py` (paid TTS)
- `docs/SECRET-ROTATION.md`, `docs/*RUNBOOK*.md`, `docs/E6-RELEASE-GATE.md`,
  `docs/EDGE-READ-BOUNDARY.md` (owner runbooks and release gates)
- `AGENTS.md`, `CLAUDE.md`, `SEED.md`, `.SEED/gotchas.md`,
  `.SEED/decisions.md` (repo rules; the two logs are append-forbidden)
- payments
- licensing
- authentication, HMAC secrets, key ids and secret rotation
- deploys: Coolify, Cloudflare Worker, DNS, environment variables, cron
- database schema or migrations in SQLite, TypeDB or the map's Supabase
- customer data: names, mobiles, emails, backups, exports, training logs
- anything that sends SMS, email, push or Facebook messages to a real person
- any change to how results are ordered or which businesses are eligible
  (the anti-bias rule)
- turning on any dark flag, or changing a default from off to on
- cross-repo contract changes with HybridCard or the LocalLoop map
- spending money: TTS providers, OpenAI model or endpoint changes, cloud
  services
- claims in `STATUS.md` about what is live in production

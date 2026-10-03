# Skills, MCP tools and conversion candidates: 3-repo inventory (looper#72)

Snapshot taken 2026-10-03 by the Behaviour Scout. All three repos were **read
only**; this file is the only change. Line numbers are from these commits:

| Repo | Short name | Commit read |
|---|---|---|
| localloop-pro/looper | **looper** | `9becb9c` (main) |
| localloop-pro/localloop.pro-main | **map** | local reference clone, 2026-10-03 |
| localloop-pro/hybridcard-v2 | **cards** | `7a0e584` |

Line numbers drift. If a citation no longer matches, search for the name in
the "What" column.

## How to read the table

- **Form**: `function` (shared code), `skill` (a `SKILL.md` an agent loads),
  `plugin`, `mcp` (an MCP tool), `leave` (leave as is).
- **Archetype**: map taxonomy (`news`, `events`, `offers`, `stays`, `jobs`,
  `dining`), plus `media` (MCP servers, plugins, media tools) and `platform`
  (auth, bridge, deploy, QA). The map's `Food` key is labelled "Dining"
  (`assets/js/category-taxonomy.js:42`), so its folder is `dining`.
- **Floors**: which repos would use it: `looper`, `map`, `cards`.
- **Risk**:
  - **HIGH (needs owner OK)**: writes data, sends SMS or email, spends money
    (including a BYOK key or a wallet fee), or calls an LLM on a platform key.
    Nothing in this column may be built without the owner's OK on its issue.
  - **med**: read-only, but unauthenticated, rate-limit-sensitive or close to a
    hot zone.
  - **low**: docs or read-only public data.
- This is documentation and routing, not access. Nothing here installs a
  plugin or MCP server or adds a credential.
- MCP tool annotations (`readOnlyHint`, `destructiveHint`) are **hints only**:
  under the MCP spec (2026-07-28, checked with Context7), clients must treat
  them as untrusted unless the server is trusted. Server-side gates (cards
  `isWrite`, looper `tool-policy.cjs`) stay the real control.

---

## A. Already a skill or MCP tool

| # | Name | What it does | Where (repo path:line) | Current form | Proposed form | Archetype | Floors | Risk | Why |
|---|---|---|---|---|---|---|---|---|---|
| A1 | ai-employees | How to build and debug the 7 AI employees, the research inbox and the autonomy gate | cards `.claude/skills/ai-employees/SKILL.md:2` | skill | leave (dedupe, see B1) | platform | cards | low | Mature skill with evals (`evals/evals.json`); only the copy is a problem |
| A2 | typedb | TypeDB/TypeQL for the geo and archetype graphs | cards `.claude/skills/typedb/SKILL.md:2` | skill | leave (dedupe, see B1, B2) | platform | cards, looper | low | looper `brain/` also writes TypeDB (`brain/sync.py:259`), so looper agents need it too |
| A3 | typesafe-ai | TypeSafe/Jev typed-judgment primitives | cards `.agents/skills/typesafe-ai/SKILL.md:2` | skill (vendor, MIT) | leave | platform | cards | low | Exists only in `.agents/`, so Claude Code agents in cards never see it |
| A4 | typeql | TypeQL 3.8 reference (1241 lines) | cards `.cursor/skills/SKILLS.md:2` | skill (wrong filename: `SKILLS.md` at the root of `.cursor/skills/`) | skill (move, see B2) | platform | cards, looper | low | Cursor won't load it as a named skill without a `typeql/SKILL.md` folder |
| A5 | branding-web-sentiment | Web and social sentiment research, then Branding Kit copy | cards `.cursor/skills/branding-web-sentiment/SKILL.md:2`; Phase 4 writes the kit at `:100` | skill (Cursor only) | skill (move, see B3) | media | cards | **HIGH (needs owner OK)**: Phase 4 populates Branding Kit content | Only Cursor sees it; a second prompt copy exists (B3) |
| A6 | better-auth | Points agents at `dox/Reference/better-auth/` before touching auth | map `.cursor/skills/better-auth/SKILL.md:2`; used at map `package.json:95` (1.7.5) | skill (Cursor only) | leave in map; share read-only with cards | platform | map, cards | med: auth is a hot zone | cards also depends on better-auth (`package.json:33`, `^1.6.19`) with no skill, on a different minor version |
| A7 | Card MCP (public, per card) | Third-party agents read a card's deals, menu, hours, contact and reviews | cards `src/app/mcp/[slug]/manifest/route.ts:11`; call route `src/app/mcp/[slug]/tool/[name]/route.ts:14`; tools `src/lib/mcp/toolRegistry.ts:16`–`:22` | mcp (bearer key `:28`, rate limit 60/min `:24`) | leave | offers, dining, stays | cards | med: manifest has no rate limit | Already the right shape. Manifest `:35` advertises an `openapi.json` route that doesn't exist |
| A8 | Card MCP `book_appointment` | Requests a booking; the executor returns a proposal plus an audit row | cards `src/lib/mcp/toolRegistry.ts:23`; executor `src/lib/mcp/executors.ts:42` | mcp tool (`isWrite: true`) | leave | stays, dining | cards | **HIGH (needs owner OK)**: marked as a write; writes an audit row | Keep the owner-approval queue in front of it |
| A9 | Owner MCP (read tools) | `employee_list`, `research_list`, `draft_list` | cards `src/lib/mcp/ownerTools.ts:28`, `:30`, `:32`; route `src/app/api/cards/[id]/mcp/tool/[name]/route.ts:13` (session auth, 60/min `:20`) | mcp | leave | platform | cards | low | Owner-scoped reads |
| A10 | Owner MCP (write tools) | `employee_run` spends BYOK plus a wallet fee; `research_add`, `draft_decide` write | cards `src/lib/mcp/ownerTools.ts:29`, `:31`, `:33` | mcp | leave | platform | cards | **HIGH (needs owner OK)**: writes and spends BYOK | Already gated by session, rate limit and the runner spine |
| A11 | Archetype skills registry | 20 card-archetype "skills" (front desk, offers, booking…) bound to card MCP tools; each targets an Anthropic model | cards `src/lib/skills/registry.ts:58` (BASE), `:79` (SUBTYPE); model `:49`–`:50` | function (in-code skill table) | leave; map its archetype ids (B6) | dining, stays, offers, events | cards | **HIGH (needs owner OK)**: calls an LLM; key source per call not traced in this pass | Closest thing to a cross-floor skill registry already; uses card archetypes (`food`, `accommodation`…), not map ones |
| A12 | looper-gateway `/mcp` (proposal tools) | `map_search_proposal`, `pins_propose_create`, `business_report_stale`, `actions_confirm`; v1 never executes writes | map `workers/looper-gateway/src/index.mjs:214` (POST), tools `:100`, `:115`, `:132`, `:154`; handler `:438` | mcp | leave; add auth and rate limit (owner) | platform | map, looper | med: **no auth and no rate limit on `/mcp`** (only CORS `:1137`) | Proposal-only today, but any future write path would land behind an open door |
| A13 | looper-gateway `/mcp` `looper_chat` | Routes through Pi `:756`, optionally to Flowise (POST `:868`) | map `workers/looper-gateway/src/index.mjs:85`; same at `/api/looper/chat` `:248` | mcp | leave; add auth and rate limit (owner) | platform | map, looper | **HIGH (needs owner OK)**: platform-key LLM (Flowise), unauthenticated | Same gap as the open-LLM item in the manager brief, on the map side |
| A14 | looper-bot read tools | `localloop_search`, `_discover`, `_businesses`, `_open_map`, `_bridge_status`, `_gateway_health` | looper `looper-bot/electron/main.cjs:169`, `:186`, `:202`, `:215`, `:231`, `:254`; wrappers `:1161`–`:1255` | function-calling tools (OpenAI Realtime) | mcp (see C1) | platform | looper | low | Already tool-shaped; other agents could reuse them through MCP |
| A15 | looper-bot `localloop_pending_pins` | Read-only pending-pin queue through the gateway's machine-auth API | looper `looper-bot/electron/main.cjs:241`; client `looper-bot/electron/localloop-gateway-tools.cjs:7`; server map `workers/looper-gateway/src/pin-read.mjs:284` | tool | leave | platform | looper, map | med: bearer token, writes an audit row on the map side | Good example of the sanctioned read path (SPEC-055) |
| A16 | looper-bot `web_search` | Exa search | looper `looper-bot/electron/main.cjs:155`; fetch `:1288` | tool | leave | media | looper | **HIGH (needs owner OK)**: spends money (Exa key) | Desktop-only, owner's own key |
| A17 | looper-bot image and thumbnail tools | `image_generate`, `thumbnail_*` (7 tools) | looper `looper-bot/electron/main.cjs:264`–`:332`; OpenAI calls `:1418`, `:1660`, `:1696` | tools | function (merge, see B9) | media | looper | **HIGH (needs owner OK)**: spends money (OpenAI images) | Two near-identical `/images/generations` calls |
| A18 | looper-bot records and computer tools | `records_create/update/delete`, `computer_*`, `screen_snapshot` | looper `looper-bot/electron/main.cjs:372`–`:513`; confirm gate `looper-bot/electron/tool-policy.cjs:12` | tools | leave | platform | looper | **HIGH (needs owner OK)**: writes local data and drives the desktop | Already behind a native confirm dialog (looper#64); never expose these over MCP |
| A19 | map Codex agents | `orc`, `search-bar-map-pro`, `cxo-strategic-advisor` | map `.codex/agents/orchestrator.toml:1`, `.codex/agents/search-bar-map.toml:1`, `.codex/agents/cxo-strategic-advisor.toml:1` | agent definitions | leave | platform | map | low | Not skills; listed so nobody re-scouts them |

## B. Duplicates to merge

| # | Name | What is duplicated | Where (every copy, path:line) | Current form | Proposed form | Archetype | Floors | Risk | Merge recommendation |
|---|---|---|---|---|---|---|---|---|---|
| B1 | ai-employees and typedb skills (`.claude` vs `.agents`) | `diff -r` shows them **byte-identical** (ai-employees 175 lines plus 14 reference files and evals; typedb 34 lines). The only difference is `typesafe-ai`, which exists only in `.agents` | cards `.claude/skills/ai-employees/SKILL.md:2` = `.agents/skills/ai-employees/SKILL.md:2`; `.claude/skills/typedb/SKILL.md:2` = `.agents/skills/typedb/SKILL.md:2`; `.agents/skills/typesafe-ai/SKILL.md:2` | skill ×2 | skill (one canonical copy) | platform | cards | low | Keep **one** canonical folder and make the other a generated mirror with a CI `diff -r` check that fails on drift. Add `typesafe-ai` to the canonical side. Which folder is canonical (and whether to use symlinks, which break on some Windows checkouts) is an owner call |
| B2 | typedb vs typeql | Two TypeDB skills: a short HybridCard-specific one and a 1241-line language reference | cards `.claude/skills/typedb/SKILL.md:2`, `.agents/skills/typedb/SKILL.md:2`, `.cursor/skills/SKILLS.md:2` (`name: typeql`) | skill ×3 | skill (typedb plus `references/typeql.md`) | platform | cards, looper | low | Move the typeql text to `typedb/references/typeql.md` in the canonical folder and link it from `typedb` SKILL.md; delete the loose `.cursor/skills/SKILLS.md` |
| B3 | branding-web-sentiment (Cursor skill vs prompt) | The same procedure as a Cursor skill and as a prompt that names it (`skill: branding-web-sentiment`) | cards `.cursor/skills/branding-web-sentiment/SKILL.md:2`, `.prompts/branding-kit/web-sentiment-research.md:3` | skill and prompt | skill (canonical folder) | media | cards | **HIGH (needs owner OK)**: populates Branding Kit | Move the skill into the canonical folder from B1 so every agent sees it; turn the prompt into a 3-line pointer |
| B4 | Bridge HMAC sign/verify (BRIDGE-CONTRACT-v1) | Same `X-HC-*`, `"{ts}.{body}"` HMAC-SHA256 scheme in 3 languages, plus a test copy | cards `src/lib/bridge/hmac.ts:15` (sign), `:27` (verify); map `workers/looper-gateway/src/bridge-hmac.mjs:110` (verify), `:144` (sign); looper `backend/services/bridge_hmac.py:29` (verify), `:62` (sign); looper `tools/e6_nonprod_check.py:62` (test signer) | function ×4 | **leave the code**; add shared golden test vectors | platform | looper, map, cards | med: frozen contract, hot zone | Don't merge code across runtimes (and the contract is frozen). Publish one JSON file of (secret, ts, body) → signature vectors, owned by cards (the sender), and have all four implementations test against it |
| B5 | Jarvis voice router and suburb coordinates | The router and its `SUBURBS` table are copied between looper and the map, and the whole `jarvis/` folder has drifted | looper `web/jarvis/voice-command-router.js:116`; map `assets/js/jarvis/voice-command-router.js:107`; looper `backend/routes/discover.py:36` (`SUBURB_COORDS`); looper `brain/data/suburbs.csv` (read at `brain/sync.py:29`) | function ×3 plus CSV | leave; extend the drift check | platform | looper, map | low | A drift check exists (looper `tools/jarvis-sync-check.js:149`, looper#39) but runs only on looper's side. Turn it into a skill (C6) and have map CI run it too |
| B6 | Archetype vocabulary | At least 6 different archetype lists: map keys `Food`/`Accommodation`/`Job-Offers`, gateway adds `fetch`/`claims`/`geo_intelligence`, cards uses `food`/`accommodation`/`retail`… | map `assets/js/category-taxonomy.js:14`; map `assets/js/agent-registry.js:12`; map `workers/looper-gateway/src/index.mjs:51`–`:60`; looper `web/jarvis/voice-command-router.js:683` (`PIN_CATEGORIES`); cards `src/types/archetypes.ts:95` (`food`), `:118` (`accommodation`); cards `src/lib/bridge/payload.ts:19` (`ARCHETYPE_TO_CATEGORY`) → map `workers/looper-gateway/src/bridge-pin.mjs:74` | constants ×6+ | function (one mapping table) | platform | looper, map, cards | low (must not reorder results) | The map taxonomy is the source of truth (it names the registry folders). Publish a read-only `archetype-map.json` from the map (map key → registry folder → cards archetype ids) and have the others read it. It only adds labels and never ranks |
| B7 | Haversine distance | 5 copies of the same formula | looper `backend/routes/search.py:13`, `brain/sync.py:66`, `brain/seed_geo.py:38`; cards `src/lib/geo/haversine.ts:4`; map `assets/js/demo-map-pins.js:804` | function ×5 | function (one per runtime) | platform | looper | low | Inside looper, `brain/` should import `backend/routes/search.py:haversine_km` (or a new `services/geo.py`). Leave the other runtimes as they are |
| B8 | slugify | Repeated slug helpers | looper `brain/sync.py:124`, `brain/seed_geo.py:49`; cards `src/lib/cards/slug.ts:8`; map `assets/js/main-map.js:1687`, also inlined in `index.html:13449` | function ×5+ | function (one per repo) | platform | looper, map | low | Card slugs are minted by cards, so other repos should read the slug from the bridge payload, not recompute it |
| B9 | OpenAI image calls in looper-bot | Two near-identical `images/generations` fetch blocks plus two `images/edits` retries | looper `looper-bot/electron/main.cjs:1418`, `:1660`, `:1696`, `:1704` | inline code | function | media | looper | **HIGH (needs owner OK)**: spends money | One `openaiImages()` helper with one place for timeout, size and error handling |
| B10 | Rate limiters | Separate limiters with different stores | looper `backend/services/edge_boundary.py:120` (in-memory); map `workers/looper-gateway/src/pin-write.mjs:221` (KV), `server/platform/rate-limit.mjs:5` (Postgres); cards `src/lib/rateLimit.ts:41` (Mongo) | function ×4 | leave; write one policy doc | platform | looper, map, cards | low | Different runtimes and stores make shared code a poor fit. Agree limits and key shapes in one doc instead |
| B11 | Looper health probes | Three probes of the same Looper search contract | map `scripts/check-looper-health.cjs:7`; looper `looper-bot/electron/main.cjs:254` (`localloop_gateway_health`); looper `tools/bench_read_paths.py:44` | script ×2 plus tool | skill (C5) | platform | looper, map | low | One "is Looper healthy" skill that runs the read-only probes in order |
| B12 | Looper API URL and `handleAIQuery` | The live map's Looper call is copied into several HTML entry points | map `index.html:15363`, `index2.html:14667`, `index001.html:12069`, `LLINDEX.html:1572`; config `scripts/inject-env.js:42` | inline code ×4 | function (map-owned) | platform | map | low | Map-side cleanup; the cross-repo contract is tracked in `docs/CROSS-REPO-CONTRACTS.md` |

## C. Conversion candidates (repeated code or hand-run routines)

| # | Name | What it does | Where (repo path:line) | Current form | Proposed form | Archetype | Floors | Risk | Why |
|---|---|---|---|---|---|---|---|---|---|
| C1 | localloop-search (read-only) | Search, discover nearby and list businesses from the Looper API | looper `backend/routes/search.py:60` (`/search`), `:232` (`/businesses`); `backend/routes/discover.py:251` (`/discover`); wrapped by looper-bot `looper-bot/electron/main.cjs:1161`, `:1186`, `:1213` | API plus desktop tools | mcp (read-only tools) | platform (serves all six archetypes) | looper, map, cards | med: public read; must sit behind looper's `edge_boundary` limits (looper `backend/services/edge_boundary.py:172`) | Three floors want "find local options": looper-bot, the gateway's `looper_chat`, and cards' Scout. One read-only MCP tool must return the API's order unchanged (never re-rank, `rank_boost` false) |
| C2 | Bridge outbox drain and status | Hand-run drain and status of the cards → map/looper bridge | cards `OPS.md:64`; `src/lib/bridge/outbox.ts:455` (`drainOutbox`); looper `backend/routes/ingest.py:316` (`/status`); looper-bot `looper-bot/electron/main.cjs:1255` (`localloopBridgeStatus`) | runbook plus code | skill (status read-only; drain stays manual) | platform | cards, looper, map | **HIGH (needs owner OK)** for drain (sends signed writes); low for status | Status is read by hand in three places. A skill can read all three; the drain stays a human step |
| C3 | Deploy and rollback | Worker deploy window, map production deploy, git revert | looper `docs/WORKER-DEPLOY-RUNBOOK.md:95` (deploy), `:160` (rollback); map `dox/runbooks/production-deploy.md:56`, `dox/runbooks/rollback.md:15`, `scripts/rollback.sh:32` | runbooks plus script | skill (checklist only, agent never deploys) | platform | looper, map, cards | **HIGH (needs owner OK)**: deploys are a hot zone | The same 0-check / note-version / deploy / verify / rollback shape is written three times |
| C4 | Backup and restore drill | Daily SQLite backup plus the monthly restore test | looper `backend/scripts/sqlite_backup.py:148` (`main`); `docs/RUNBOOK-BACKUP-RESTORE.md:95` (restore), `:186` (monthly test) | script plus runbook | skill (guided drill on a copy) | platform | looper | **HIGH (needs owner OK)**: a restore overwrites data | The monthly drill is a 15-minute hand routine; a skill can walk it on a throwaway copy only |
| C5 | Release smoke and SLO gate | Non-prod contract and load checks, SLO report, read-path bench, map smoke checklist | looper `tools/e6_nonprod_check.py:211`, `tools/slo_report.py:123`, `tools/bench_read_paths.py:44`, `docs/E6-RELEASE-GATE.md:120`; map `dox/runbooks/release-smoke.md:31`, `scripts/check-looper-health.cjs:7` | scripts plus runbooks | skill | platform | looper, map | med: `e6_nonprod_check` sends signed test writes; host guard `:202` must stay | Gives every PR's "before/after numbers" (manager brief §2) one repeatable routine |
| C6 | Jarvis sync check | Checks the voice router's suburbs and wake words against `/api/discover` and the map's copy | looper `tools/jarvis-sync-check.js:149` | script | skill (wraps the script) | platform | looper, map | low | Drift between the two `jarvis/` copies is real (B5); a skill makes the check part of map PRs, not just looper's |
| C7 | Secret and key rotation | Rotate Looper, Supabase and Mapbox keys | looper `docs/SECRET-ROTATION.md:28`; map `dox/runbooks/supabase-rotation.md:11`, `dox/runbooks/mapbox-rotation.md:11` | runbooks | leave (human-only) | platform | looper, map | **HIGH (needs owner OK)**: credentials | Agents must never hold or print secrets. Keep these as human runbooks; at most a skill that links the right one |
| C8 | Grill-me loop | Plan → Grill-me (self-answer plus questions) → Act, with JSON schemas | cards `src/lib/office/plan.ts:42` (grill schema), `:149` (`createActivePlan`), `:206` (`applyGrillRound`); model calls `src/lib/office/chat.ts:612` (`runGrillMode`) | product code (owner Office) | skill (process doc for agents; product code untouched) | platform | looper, map, cards | low (doc only); the product version spends BYOK via `src/lib/ai/client.ts:134` | Every floor's agents are asked to grill before acting; one shared SKILL.md beats re-describing it per repo |
| C9 | Issue triage (Jev) | Labels GitHub issues with TypeSafe Jev | cards `scripts/jev-issue-triage.mjs:209` (`main`), key at `:83` | script plus workflow | skill (later, if the owner wants it on all floors) | platform | cards | **HIGH (needs owner OK)**: platform-key LLM and writes labels | Useful across all three repos, but it spends a platform key |
| C10 | News to audio | Turns `news_post` rows into MP3 (OpenAI TTS), uploads them and sets `audio_url` | looper `tools/news_audio_worker.py:150` (`run`), TTS `:93`, write `:128` | scheduled script | leave | news | looper, map | **HIGH (needs owner OK)**: writes Supabase, spends TTS | Already a scheduled task; nothing to gain from wrapping it |
| C11 | Facebook review import | Classifies group posts and imports them as businesses or reviews | looper `backend/services/facebook_pipeline.py:185` (`run_pipeline`), `:64` (`classify_post`), `:130` (`import_to_db`) | function | leave | news, dining | looper | **HIGH (needs owner OK)**: writes the DB; source text may contain PII | Hot zone (customer data). A skill would only document the review steps |
| C12 | TypeDB brain sync | Syncs businesses and suburbs into TypeDB; runs migrations; seeds geo | looper `brain/sync.py:259` (`sync_business`), `brain/migrate.py:49`, `brain/seed_geo.py:113` | functions plus CLI | leave (covered by the typedb skill, A2) | platform | looper | **HIGH (needs owner OK)**: writes TypeDB, migrations | The typedb skill should be readable from looper too (B2) |
| C13 | Demo and seed data | Seeds demo businesses and reviews | looper `backend/seed.py:10`; map `scripts/seed-bondi-demo.mjs:30`; cards `scripts/seed-bookings.ts:145` | scripts | leave (**do not convert**) | platform | looper, map, cards | **HIGH (needs owner OK)**: writes data | BLIND-SPOTS §5 says never seed fake data into production. Making seeding easier is the wrong direction |
| C14 | Pin moderation | Admin approves or rejects pending pins | map `workers/looper-gateway/src/pin-moderate.mjs:142`; cards `OPS.md:93` (pin approval) | route plus runbook | leave | platform | map, cards | **HIGH (needs owner OK)**: writes, admin | Read side is already a tool (A15); the write stays human |
| C15 | Card knowledge for Looper | Builds the public-safe knowledge blob Looper uses for a card | cards `src/lib/looper/knowledge.ts:130` (`buildCardKnowledge`) | function | leave (cards-owned) | platform | cards, looper | med: must stay public-safe (no PII) | Consumers should read it through the bridge, not copy it |
| C16 | Wallet and payment recovery | Credit a dev wallet; recover a Polar checkout that never credited | cards `scripts/credit-dev-wallet.mjs:81`, `scripts/credit-polar-checkout.mjs:46` | scripts | leave (**do not convert**) | platform | cards | **HIGH (needs owner OK)**: payments hot zone | Listed so nobody proposes it |
| C17 | Training export | Exports reviews to JSONL or a HuggingFace dataset | looper `training/export.py:8`, `:44` | script | leave | platform | looper | **HIGH (needs owner OK)**: moves data out of the system; PII check needed | Must pass a PII review before any wider use |

## Gaps found while scouting (routed, not fixed here)

These are not conversions. Each needs its owner, and none was changed by this
PR:

1. **map `/mcp` and `/api/looper/chat` have no auth and no rate limit**, and
   `looper_chat` can call Flowise on a platform key (`workers/looper-gateway/src/index.mjs:214`,
   `:248`, `:868`). This is the same class of problem as the "open LLM endpoint"
   item in the manager's brief, on the map side.
2. cards' employee tick has no Coolify task: `CRON.md:14` lists it, but the
   setup only creates tasks 1–4. Scheduled Scout runs may never fire.
3. cards `finn_snapshot` exists only as a name (`src/lib/aiEmployees/roster.ts:62`).
   Only Scout and Leo are registered (`src/lib/aiEmployees/runner.ts:30`–`:31`).
4. cards platform-key LLM paths: `src/app/api/cards/extract/route.ts:70`
   (Anthropic) and `src/lib/aiEmployees/suggestModel.ts:63` (TypeSafe). Both
   are rate-limited, but they spend the platform key.

## Top 5 conversions most worth doing

| Rank | Conversion | Rows | Home repo | Shared with | Why first |
|---|---|---|---|---|---|
| 1 | **One canonical skills folder in cards** (dedupe `.claude`/`.agents`, move typeql and branding-web-sentiment in, CI drift check) | B1, B2, B3, A3–A5 | **hybridcard-v2** | looper and map agents read it | Zero runtime risk, removes three silent-drift copies, and makes 2 hidden skills visible to every agent |
| 2 | **`localloop-search` read-only MCP tool** over `/search`, `/discover`, `/businesses` | C1, A14 | **looper** (owns the API and the edge rate limits) | map gateway `looper_chat`, cards Scout | Three floors re-implement "find local options". One read-only tool, behind auth and per-IP limits, returning the API's order unchanged |
| 3 | **Archetype mapping table** (`archetype-map.json`) | B6 | **localloop.pro-main** (owns the taxonomy) | looper registry folders, cards archetypes, gateway keywords | Six vocabularies drift today; the skills registry folders depend on it. Labels only, never ranking |
| 4 | **Bridge HMAC golden test vectors** | B4 | **hybridcard-v2** (bridge sender, frozen contract) | looper `bridge_hmac.py`, map `bridge-hmac.mjs`, looper `e6_nonprod_check.py` | Four implementations of a frozen contract with no shared proof they agree. Tests only, no contract change |
| 5 | **"Looper healthy?" release-smoke skill** (health probe, jarvis sync, bench, SLO report) | C5, C6, B11, B5 | **looper** | map runs the same probes in its CI | Gives every PR the before/after numbers the brief asks for, and catches jarvis drift from both sides. Read-only |

Not in the top 5 on purpose: anything that deploys, restores, rotates keys,
seeds data, moves money or sends messages (C3, C4, C7, C13, C16). Those stay
human runbooks until the owner says otherwise.

## Next steps

- One registry file per entry under `.SEED/skills/<archetype>/<slug>.md`, after
  `.SEED/skills/GRILL-ME.md` settles the folder structure (separate issue).
  This inventory is a snapshot: update the registry files, not this table
  (looper#53).
- Each top-5 item that lives in another repo gets a "Skill: …" issue in that
  repo with acceptance criteria. The owner's OK goes on any HIGH item before
  work starts.

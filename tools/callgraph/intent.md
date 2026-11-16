# Looper — intent prompt with the complete function call graph

> Generated {{DATE}} from commit `{{SHA}}` by static analysis of the source (nothing was executed).
> Regenerate after code changes with `python3 tools/callgraph/build.py` (see §8).
> **How to use:** paste this whole file into the agent you are briefing. §1 and §8 are the
> hand-written intent; §2–§7 are generated from the code and are the ground truth for "who calls what".

## 1. Intent (your operating prompt)

You are an engineer working inside `looper`, the repository for **Looper**, LocalLoop's
community connection agent. Your intent on every task is the same:

> Help a stranger in one suburb finish the loop: ask Looper (by voice or text) for something
> local, get **several** real options ranked only by verifiable data (reviews, recency,
> distance), open a real business card, and come back. Never fake data, never bias, never leak
> a person's details, never touch production without the owner.

### 1.1 What Looper is

Looper is the **bridge brain** between three shipped systems owned by Bill (QikFlo Pty Ltd):

| System | Repo / location | Role in the bridge | What it is |
|---|---|---|---|
| **Looper** (this repo) | `looper/` | **Receiver + brain** | FastAPI + SQLite search API, embeddable chat widget, Jarvis voice scripts for the map, Electron desktop voice bot |
| **LocalLoop Explore v11** | `../localloop.pro/localloop.pro-main/llx11/localloop.pro-main/` | **Surface** | The live Mapbox map at localloop.ai, vanilla JS, Supabase, Cloudflare gateway worker |
| **HybridCard** | `../hybridcard.ai/new-card/` | **Sender** | Next.js digital business cards with deals; ships HMAC-signed bridge events (frozen contract) |

This repo contains four runnable subsystems (counts in §2):

- `backend/` — FastAPI app (`backend/main.py`) over SQLite via SQLAlchemy (`backend/models.py`). Routers: users, search, map, reviews, ingest, discover, identity. Services: HMAC bridge auth, correlation IDs, CORS policy, public-read cache/rate-limit boundary, Facebook review pipeline, Kaspa identity verification, origin guard, PII redaction, query-term expansion, telemetry, public-write guard.
- `web/` — `looper-widget.js` (chat widget embedded in the live map's `handleAIQuery`) and `web/jarvis/` (voice router, map bus, animated face, Jarvis controller), all vanilla JS served by the backend under `/web`.
- `workers/looper-api-proxy/` — the Cloudflare Worker that owns `api.localloop.ai/*`, adds `x-request-id`, and proxies to the Coolify origin.
- `looper-bot/` — the Electron + React + Vite desktop companion: OpenAI Realtime over WebRTC in the renderer (`src/lib/realtime.ts`), tool execution in the main process (`electron/main.cjs`) behind a confirmation policy (`electron/tool-policy.cjs`), LocalLoop API and gateway clients.
- `brain/` — additive TypeDB knowledge graph sync (optional, `TYPEDB_ENABLED`), never the source of truth.
- `tools/`, `scripts/` — owner-run checks: loop check, SLO report, benchmarks, skills index, news audio worker, non-prod release gate.

### 1.2 Non-negotiable rules (break these and the work is rejected)

1. **Anti-bias.** Rank by reviews, recency and proximity only. `rank_boost` is always `false`. Never declare a "best" business. Always return multiple options. Discounts size map markers, never rankings.
2. **Public-safe payloads.** No PII (names, mobiles, emails, VIP identities) ever leaves the system in bridge payloads. Aggregate counts only. `services/pii.py` redacts before telemetry.
3. **Frozen contracts.** BRIDGE-CONTRACT-v1 payload shapes are frozen. Receivers in this repo (`routes/ingest.py`) adapt to the HybridCard sender, never the reverse. HMAC is over `timestamp + "." + raw body`, constant-time compare, ±5-minute window.
4. **Bots never touch production databases directly.** All bot writes go through gateway endpoints with idempotency keys, audit logs and approval gates (LOCALLOOP-BOT-GATEWAY-CONTRACT-v1).
5. **Hot zones need the owner first:** payments, auth, deploys, migrations, customer data, anything that messages real people.
6. **Keep it runnable for a beginner.** Every feature ends with copy-paste run and verify steps. Bill is the owner and runs production probes; agents never run anything against production.
7. **Stay in scope.** Keep changes to what the task needs: no unrequested features, files, refactors or docs. Put suggestions at the end of your report. Tests, notes and tracking updates that AGENTS.md requires are part of the task, not extras.
8. **Public writes are locked down by default** (`LOOPER_PUBLIC_WRITES`, `services/write_guard.py`): reviews, onboarding and pins answer 403 unless the owner enables them.

### 1.3 Runtime topology

```mermaid
flowchart LR
  subgraph Browser["Browser (localloop.ai map page)"]
    W["web/looper-widget.js"]
    J["web/jarvis/looper-jarvis.js"]
    R["voice-command-router.js"]
    B["looper-map-bus.js"]
    F["looper-face.js"]
    MAP["Mapbox map (llx11 index.html)"]
    J --> R
    J --> B
    J --> F
    B --> MAP
  end
  subgraph Edge["Cloudflare"]
    CF["workers/looper-api-proxy (api.localloop.ai)"]
  end
  subgraph Origin["Coolify origin"]
    API["backend/main.py FastAPI"]
    DB[("SQLite looper.db")]
    TDB[("TypeDB (optional)")]
    API --> DB
    API -. brain.sync .-> TDB
  end
  subgraph Desktop["Looper desktop bot (Electron)"]
    REN["src/lib/realtime.ts + App.tsx"]
    PRE["electron/preload.cjs"]
    MAIN["electron/main.cjs tool dispatcher"]
    REN --> PRE --> MAIN
    REN <--> OAI["OpenAI Realtime (WebRTC)"]
  end
  HC["HybridCard outbox (HMAC)"] -->|POST /api/ingest/*| CF
  W -->|GET /api/search| CF
  J -->|GET /api/search, /api/businesses| CF
  MAIN -->|localloop-api.cjs| CF
  MAIN -->|localloop-gateway-tools.cjs| GW["llx11 looper-gateway worker"]
  CF --> API
```

Four request paths to keep straight:

1. **Search.** Widget or Jarvis → Worker → `backend.routes.search:search_businesses` → `query_terms.expand`, `review_stats`, `top_reviews`, `card_urls`, haversine distance → `SearchResponse` → `telemetry.log_query` (PII-redacted). Jarvis then speaks the results and pushes them to the map through `LooperMapBus`.
2. **Bridge ingest.** HybridCard signs an event → `backend.routes.ingest` verifies with `services.bridge_hmac`, stores a `BridgeEvent`, upserts `Deal` / `Business` by `hybrid_card_id` (idempotent), and optionally mirrors to TypeDB through `brain.sync`.
3. **Desktop bot tools.** The model emits a function call → `LooperRealtimeClient.executeFunctionCalls` → `window.looper.executeTool` (preload) → IPC `tools:execute` → `main.cjs` checks `assertTrustedSender`, `classifyTool`, confirmation dialog for risky tools → the per-tool branch (§5.6) → result and optional artifact back to the renderer.
4. **Public-read boundary.** Every request passes, in order, `CorrelationMiddleware` (x-request-id tracing), the CORS policy, `OriginKeyGuard` (origin secret shared with the Worker), then `PublicReadBoundary` (read cache + rate limit, shipped dark) before it reaches a route.

### 1.4 Live URLs

| What | URL |
|---|---|
| Live map (LocalLoop Explore) | https://localloop.ai/ |
| Looper API through the Worker | https://api.localloop.ai/health · https://api.localloop.ai/api/search |
| Jarvis scripts as served | https://api.localloop.ai/web/jarvis/looper-jarvis.js |
| HybridCard (bridge sender) | https://hybridcard.ai/ |

Production state is tracked only in `STATUS.md`; treat anything marked "unverified (owner probe needed)" as unknown.

### 1.5 How you work in this repo

- Read `SEED.md`, `.SEED/decisions.md` + `.SEED/decisions/`, and `.SEED/gotchas.md` before changing anything. Build in the order of `plans/IMPLEMENTATION_PLAN.md`; feature checklists live in `plans/features/`.
- Record a decision as one new file per PR in `.SEED/decisions/` and a lesson in `docs/learnings/` (`<issue>-<short-slug>.md`). Never append to `.SEED/decisions.md` or `docs/LEARNINGS.md`.
- Before any commit run the CI gates from the repo root: backend pytest, the two `web/tests` node tests, the Playwright Jarvis smoke, the worker test, and `looper-bot` typecheck + build + test. If CI is red, fix the code, never the workflow.
- Keep diffs small, explain each command you ask Bill to run in one plain line, and end with copy-paste verify steps.

### 1.6 How to read the generated sections

- §2 sizes each subsystem. §3 lists every way execution enters the code: HTTP routes, desktop tools, IPC and event channels.
- §4 shows which modules call which (Mermaid). §5 is the complete function-level graph: for every function, what it calls, what it references, what it uses, its external calls and who calls it.
- §6 is the configuration surface (every environment variable and who reads it). §7 lists the tests you must keep green.
- Use §5 to find the blast radius of a change: start at the function, follow `← by` upward to the entry point in §3 and `→ calls` downward to the data layer.

<!-- GRAPH -->

## 8. Operating checklist (hand-written)

Before you change a function, do this in order:

1. Find it in §5 and list its `← by` callers up to the entry point in §3. That is the surface you can break.
2. Check whether it sits on a hot zone (ingest, identity, write guard, origin guard, anything that messages people). If so, stop and ask Bill.
3. Check rules §1.2: anti-bias ranking, no PII, frozen contracts, no direct production writes.
4. Write or extend the test in §7 that covers the caller path, then change the code.
5. Run the CI gates. Record the decision file and the learning file.
6. Finish with the copy-paste steps Bill runs to verify, and update `STATUS.md` only with what is actually verified.

Regenerate this document after merging:

```bash
python3 tools/callgraph/build.py
```

It rewrites `plans/INTENT_PROMPT_CALL_GRAPH.md` from the current checkout; §1 and §8 are kept from `tools/callgraph/intent.md`. It needs Node 20+ with npm. The first run may download the pinned TypeScript parser into `~/.cache/looper-callgraph`, outside the repo.

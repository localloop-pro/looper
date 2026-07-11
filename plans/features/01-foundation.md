# 01 — Phase 0 — Foundation (blocks everything)

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F0.1** — Repo scaffolding + knowledge base (looper)
- [ ] **F0.2** — Everything runs locally (one command each)
- [ ] **F0.3** — Secrets + env master table (generate once, store in Coolify + local `.env`s)
- [ ] **F0.4** — Dockerize the looper backend

---


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

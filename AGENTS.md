# AGENTS.md — looper repo rules

> **Read @SEED.md first.** It is the knowledge index for this repo. Then read
> `.SEED/decisions.md` (decisions already made) and `.SEED/gotchas.md`
> (mistakes we never repeat) before changing anything.

## What this repo is

LOOPER — the LocalLoop community connection agent. Two subsystems:

- `looper-bot/` — "Looper" Electron + React + Vite voice companion (OpenAI
  Realtime API over WebRTC, tool-calling, artifact panel). The Jarvis-like
  interface.
- `backend/` — FastAPI + SQLite community search API (businesses, reviews,
  map pins, onboarding, Facebook import pipeline). Serves the embeddable
  `web/looper-widget.js`.

The master build plan for bridging looper ↔ LocalLoop Explore (llx11) ↔
HybridCard lives at `plans/IMPLEMENTATION_PLAN.md`. Implement features in the
order that plan defines.

## Non-negotiable rules

1. **Anti-bias:** never rank businesses by anything other than verifiable data
   (reviews, recency, proximity). Never declare a "best" business. Always show
   multiple options. `rank_boost` is always `false`. Discounts size markers,
   never rankings.
2. **Public-safe payloads:** no PII (names, mobiles, emails, VIP identities)
   ever leaves this system in bridge payloads. Aggregate counts only.
3. **Frozen contracts:** BRIDGE-CONTRACT-v1 payload shapes are frozen —
   receivers in this repo adapt to the HybridCard sender, never the reverse.
4. **Bots never touch production DBs directly** — all bot writes go through
   gateway endpoints with idempotency keys, audit logs, and approval gates
   (see LOCALLOOP-BOT-GATEWAY-CONTRACT-v1).
5. **Hot zones — ask the owner first:** payments, auth, deploys, migrations,
   customer data, anything that sends SMS/messages to real people.
6. **Keep it runnable for a beginner:** the owner (Bill) is a basic coder.
   Every feature must end with simple copy-paste run/verify steps.

## Quality gates before any commit

These are exactly the commands `.github/workflows/ci.yml` runs on every PR to
`main` (plus a gitleaks secret scan). Run them from the repo root:

```bash
# backend (Python 3.12)
cd backend && python3 -m venv .venv \
  && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt \
  && .venv/bin/python -m pytest -q && cd ..
# web (Node 20+)
node web/tests/voice-command-router.test.js
node web/tests/jarvis-sync.test.js
# worker
node workers/looper-api-proxy/test/index.test.mjs
# looper-bot (ELECTRON_SKIP_BINARY_DOWNLOAD=1 skips the Electron download)
cd looper-bot && npm ci && npm run typecheck && npm run build && npm test && cd ..
```

If CI is red, fix the code, never the workflow (see the header of `ci.yml`).

## Key cross-repo links

- LocalLoop Explore v11 (live map, static JS + Supabase + Cloudflare worker):
  `../localloop.pro/localloop.pro-main/llx11/localloop.pro-main/`
- HybridCard (Next.js card product, bridge SENDER):
  `../hybridcard.ai/new-card/`
- Old voice-control build (port source, do not deploy):
  `../localloop.ai/golive_LocalLoop_Explore_html/explore-local.tsx`

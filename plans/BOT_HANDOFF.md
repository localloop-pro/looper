# BOT_HANDOFF.md — give this file to any coding agent

**Date:** 2026-07-18 · **Owner:** Bill (QikFlo Pty Ltd) · **Repo:** `localloop-pro/looper`

You are building out LOOPER — the brain behind the LocalLoop Explore map.
This file is your single entry point. Everything you need is already written
down in this repo; your job is to execute the remaining features in order.

## 1. Orientation (read these, in this order, before any code)

1. `SEED.md` — what this project is, folder map, key docs.
2. `AGENTS.md` — the non-negotiable rules (anti-bias, no PII, frozen
   contracts, hot zones, quality gates).
3. `.SEED/decisions.md` — decisions already made. Never re-litigate them.
4. `.SEED/gotchas.md` — mistakes already made once. Never repeat them.
5. `plans/IMPLEMENTATION_PLAN.md` — the master plan (authoritative).
6. `plans/features/01-…10-*.md` — per-feature working files with checklists.
   Work from these; tick a box only when its Acceptance criteria all pass.

## 2. Current status (as of 2026-07-18)

| Phase | Status |
|---|---|
| 0 Foundation (F0.1–F0.4) | ✅ done |
| 1 Bridge (F1.1–F1.4) | ✅ built + committed (looper receivers with 39 tests; llx11 worker `bridge-pin.mjs` + `hybridcard-markers.js` on llx11 `main`) |
| 1 F1.5 staging dry run | ⏳ phase 1 done locally; remaining: approve test pin, `removed` phase, retire test pin, true staging deploy (Bill is doing these with an agent via browser) |
| 2 Brain (TypeDB) · 3 Voice · 4 Jarvis · 5 Card↔map · 6 News audio · 7 loop-onboard · 8 Districts · 9 Deploy | ⬜ not started |

Live wiring today: llx11 `index.html` `handleAIQuery` already calls
`{looperApi}/api/search` first (anti-bias results, ⭐, spoken summary,
graceful fallback) — but `window.LocalLoopConfig.looperApi` defaults to
`http://localhost:8000`, so production falls back to local search until
`api.localloop.ai` exists (F9.1, being pulled forward with F1.5 staging).

## 3. Build order (what you do next)

Implement features ONE AT A TIME in this order, from the feature files:

1. **Phase 3 — Voice** (`plans/features/04-voice.md`, F3.1→F3.4). Bill's
   priority: the map already has a voice dock; unify it and make answers come
   from the LOOPER brain. F3.1 audit first — evidence before code. All llx11
   edits are surgical + additive (new JS files, one script include each);
   `index.html` is a ~517KB monolith — never regenerate it.
2. **Phase 2 — TypeDB brain** (`plans/features/03-typedb-brain.md`,
   F2.1→F2.5). Additive only: TypeDB down must never block ingest or search.
   On Bill's machine TypeDB already listens on port 8000 — run the backend
   with `LOOPER_PORT=8010` locally.
3. **Phase 4 — Jarvis** (`plans/features/05-jarvis.md`). F4.1 can start any
   time (needs only the local backend); F4.3 needs F1.5 finished.
4. Then Phases 5 → 6 → 7 → 8 → 9 per their feature files.

Parallel-safe tracks (if running multiple agents): Phase 2, Phase 3, Phase 6,
Phase 7 are independent of each other once Phase 0/1 are done. Phases 4, 5,
8, 9 stitch them together. NOTE: llx11 and new-card have other active,
concurrent work streams — re-check `git status` in every repo immediately
before committing, touch only the files your feature names, and never commit
someone else's in-flight changes.

## 4. Rules that override everything you might prefer

- **Anti-bias:** rank by reviews + recency + proximity ONLY. `rank_boost`
  always `false`. Never one "best" — always multiple options.
- **No PII** in any cross-system payload. Aggregate counts only.
- **Frozen contracts:** BRIDGE-CONTRACT-v1 (new-card/planning) — receivers
  adapt, never the sender. HMAC over raw body, ±5 min, idempotent on
  `eventId`, `active:false` = deactivate, never delete.
- **Hot zones — stop and ask Bill:** payments, auth, deploys, migrations,
  prod Supabase writes, anything messaging real people.
- **Quality gates before any commit:**
  `cd backend && python -m pytest` · `cd looper-bot && npm run typecheck && npm run build`.
- **Every feature ends with copy-paste run/verify steps a beginner can run**,
  and evidence in `plans/evidence/<feature>/`.
- Log new decisions in `.SEED/decisions.md`, new traps in `.SEED/gotchas.md`,
  tick the feature checklist, and update `SEED.md`'s "Next steps" when done.

## 5. Known open items you may hit

- **R2 / eventId:** the T2 card-payload spec omitted `event_id`; a proposal
  to add it (mirroring the deal payload) is at
  `new-card/plan/project-vip-live-alerts/bot-task-phase/localloop-waze-bridge/PROPOSAL-add-event-id-to-card-payload.md`.
  Our receiver `/api/ingest/hybridcard-card` requires it — keep it that way
  unless Bill says otherwise.
- **Accent gotcha:** backend search is accent-sensitive ("café" vs "cafe") —
  normalize accents when F3.3 lands (voice transcripts will say "cafe").
- **Widget hardcode:** `web/looper-widget.js` hardcodes
  `http://localhost:8000/api` — F3.3 makes it configurable.
- **F5.2 open question:** should a deal content-edit force re-moderation of
  an approved pin? Ask Bill when you reach F5.1/F5.2.
- Uncommitted looper-bot fixes (mic permission, env override, renderer log
  mirroring) may exist on `main` — run the quality gates and commit them
  first if still present.

## 6. Cross-repo paths (relative to this repo's parent)

- llx11 map site: `../localloop.pro/localloop.pro-main/llx11/localloop.pro-main/`
- HybridCard sender: `../hybridcard.ai/new-card/`
- Old voice build (port source only, never deploy):
  `../localloop.ai/golive_LocalLoop_Explore_html/explore-local.tsx`

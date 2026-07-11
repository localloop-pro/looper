# SEED.md — looper Knowledge Index

Last updated: 2026-07-11

## What this project is

LOOPER — LocalLoop's community connection agent ("Ricky" / Jarvis-like voice
bot + FastAPI search backend). Owner: Bill / QikFlo Pty Ltd. This repo is the
**bridge brain** between three systems:

- **LocalLoop Explore v11** (`llx11/localloop.pro-main`) — the live Mapbox map
  of local businesses (localloop.ai / localloop.pro).
- **HybridCard** (`hybridcard.ai/new-card`) — digital business cards with
  deals; SENDER of the HMAC bridge events.
- **Bondi Local Loop** — 156K-member Facebook group feeding members and news.

## Folder map

- `looper-bot/` — Electron voice companion (OpenAI Realtime over WebRTC,
  23 tools, artifact panel, animated face). The Jarvis UI.
- `backend/` — FastAPI + SQLite: search, onboarding, reviews, map pins,
  Facebook review-import pipeline (`services/facebook_pipeline.py`).
- `web/` — embeddable `looper-widget.js` chat widget (already wired into
  llx11 `index.html` `handleAIQuery`).
- `training/` — training-data export (HuggingFace JSONL).
- `plans/` — **`IMPLEMENTATION_PLAN.md` = master bridge plan. Start here.**
  Per-feature working files with checklists: `plans/features/01-…10-*.md`.

## Key documents

- `plans/IMPLEMENTATION_PLAN.md` — the master plan: bridge looper ↔ llx11 map
  ↔ HybridCard, voice map control, TypeDB brain, multi-district onboarding
  bot, geo-locked news/podcast, Coolify deploy.
- `AGENTS.md` / `CLAUDE.md` — repo rules for coding agents.
- `.SEED/decisions.md` — decisions log. `.SEED/gotchas.md` — never repeat.
- Frozen upstream contracts (live in new-card repo, copies referenced):
  `planning/BRIDGE-CONTRACT-v1.md`, `planning/LOCALLOOP-BOT-GATEWAY-CONTRACT-v1.md`,
  `planning/TYPEDB-GEO-HIERARCHY-SPEC.md`.

## Sites

- localloop.ai — live LocalLoop Explore map (Site A, static JS + Supabase).
- hybridcard.ai — live HybridCard product (Next.js 16 + Mongo, Coolify).
- Facebook: facebook.com/groups/BondiLocalLoop (156K) + Byron Bay (6K).

## Next steps

- Implement `plans/features/` in order (01-foundation → …); tick each
  feature's checklist box when its Acceptance passes. Split done 2026-07-11.

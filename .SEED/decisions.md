# .SEED/decisions.md — looper decisions log

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

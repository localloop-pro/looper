# 07 — Phase 6 — News → geo-locked audio (the podcast layer)

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F6.1** — News audio worker (text → voice → `audio_url`)
- [ ] **F6.2** — Server-side geo lock for news
- [ ] **F6.3** — Community sentiment tag on news (light-touch, P2)

---


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

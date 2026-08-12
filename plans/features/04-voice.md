# 04 — Phase 3 — The Voice: old-build grammar into llx11's MicWave

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F3.1** — Voice gap audit (evidence first, code second)
- [ ] **F3.2** — Shared voice command router (one grammar, both entry points)
- [ ] **F3.3** — Voice answers come from the LOOPER brain
- [ ] **F3.4** — `LooperMapBus`: one documented control surface for the map

> **2026-07-12 progress (see `.SEED/decisions.md`):** the F3.2 router
> (ported grammar + bug fixes, 46 unit tests), the F3.4 bus, and the F3.3
> speak-from-the-brain flow (chunked TTS, barge-in, anti-bias summaries,
> configurable API base incl. `web/looper-widget.js`) are BUILT in this repo
> as embeddables under `web/jarvis/` + demo at `GET /demo`. Backend accent
> normalization landed (`fold_accents`). Boxes stay unticked until the
> modules are wired into llx11's MicWave/main-map entry points and the
> acceptance passes there (integration snippet: README "Embedding on the
> live map").
>
> **2026-08-12 cross-repo confirmation:** LocalLoop confirmed the live llx11
> source now loads the five Jarvis scripts in the required defer order and
> binds `LooperMapBus`; `applyDeepLinks()` and host listening/idle state sync
> are wired. LocalLoop PR #75 merged to main as `158299a`; install/secret
> scan, unit/integration, Playwright E2E, and `ci-required` were all green,
> and tracking issue #77 closed. Remaining acceptance evidence is
> narrower than the old note: add direct mocked-map coverage for
> `looper-map-bus.js`, direct `applyDeepLinks()` coverage, then Bill performs
> the real Chrome mic / Firefox typed-fallback checklist. Do not mark F3.x
> complete before those manual/direct-contract gates pass.

---


> llx11 ALREADY has: "Hey Looper" wake word (Porcupine), Web Speech
> single-shot recognition, the MicWave dock UI, basic category/radius/zoom
> commands, `speakResponse()` TTS, and `askSwarm()` with a `<map>` tag →
> suburb flyTo. Phase 3 does NOT rebuild any of that — it unifies it and
> ports what the OLD build had that llx11 lacks.

---

**F3.1 — Voice gap audit (evidence first, code second)**

- **What:** A written checklist comparing the old build's grammar (§2.4)
  against llx11's current voice router(s) (`assets/js/main-map.js` +
  `assets/js/voice-listening-ui.js` — note the known "duplicate logic, keep
  in sync" warning in `plans/MicWave.md`).
- **Output:** `plans/evidence/F3.1-voice-gap-audit.md` in llx11 listing per
  command: works / missing / broken, with a screen recording of each.
- **Expected gaps (verify, don't assume):** specific-business "find/show/
  tell me about X" regex → flyTo; radius phrase parsing ("within 2 km",
  "near me"); natural synonyms (hungry/eat/stay/relax/work); best-offer
  intent; booking intent; fitBounds-over-category-results; TTS chunking for
  >200-char replies; barge-in cancel; explicit "zoom in/out/reset" verbs
  (old build lacked them too — add new).
- **Acceptance:** checklist reviewed by Bill; each gap becomes a checkbox
  F3.2 must tick.
- **Depends:** F0.2 (llx11 running locally). Parallel-safe with Phases 1–2.

---

**F3.2 — Shared voice command router (one grammar, both entry points)**

- **What:** Extract `assets/js/voice-command-router.js` (new, framework-free
  IIFE like the site's other modules): input = final transcript string +
  context (map center, active category, radius); output = a **command
  object** `{intent, category?, subcategory?, radiusM?, businessName?,
  suburb?, speak?:string}` — NO direct map calls inside the router (pure,
  unit-testable).
  Port from the old build (with fixes): stop (word-boundary regex, not
  substring), radius parsing incl. "near me" → 1000 m, category + synonym
  table mapped to the **fixed pin categories** (hungry/eat → `Food`,
  stay/hotel → `Accommodation`, deal/offer → `Offers`, job/work →
  `Job-Offers`, news → `News`, event → `Events`, delivery/courier →
  `Fetch_Deliveries`), specific-business regex, best-offer, booking intent,
  "take me to <suburb>" (delegates to the existing askSwarm geocode path),
  NEW: "zoom in/out", "reset view". Fix the stale-radius bug: the command
  object carries the parsed radius, consumers never read stale state.
  Wire BOTH existing entry points (`main-map.js` handler + MicWave dock) to
  this one router; delete the duplicated logic.
- **Files:** `assets/js/voice-command-router.js` (new),
  `tests/voice-command-router.unit.js` (new, node-runnable like the
  gateway's unit tests), surgical call-site swaps in `main-map.js` +
  `voice-listening-ui.js`, `<script>` include in `index.html`.
- **Acceptance:** unit tests cover ≥25 utterances → expected command
  objects (including the misfire case: "bus stop near me" must NOT trigger
  stop); manual: the F3.1 checklist all green in Chrome; Firefox falls back
  to typed input without console errors.
- **Depends:** F3.1.

---

**F3.3 — Voice answers come from the LOOPER brain**

- **What:** When the router yields a search-like intent, call the LOOPER API
  (`/api/search` or `/api/discover` with lat/lng/radius/category), then
  (a) SPEAK an anti-bias summary ("I found 4 cafés within 1 km — Gertrude &
  Alice has 5 stars from 12 reviews…", chunked >200 chars, cancel on
  barge-in), and (b) act on the map via the bus (F3.4): drop/refresh result
  pins, `fitBounds` over them (padding 50, maxZoom 15).
  Make the widget/API base configurable:
  `window.LocalLoopConfig.looperApi` (exists) — default
  `https://api.localloop.ai` in prod injection, localhost:8000 in dev.
  Graceful degrade: LOOPER down → existing local search path (current
  behaviour), spoken apology.
- **Files:** surgical edits in the `handleAIQuery` integration area of
  `index.html` / `main-map.js`; `web/looper-widget.js` in looper repo (read
  API base from config instead of hardcoded localhost).
- **Acceptance:** say "find me a café" → spoken multi-option answer with
  review counts + map fits bounds to those pins; kill looper-api → same
  utterance still answers from local search; no ranking by discount
  anywhere.
- **Depends:** F3.2 (+ F2.3 optional — works against `/api/search` alone).

---

**F3.4 — `LooperMapBus`: one documented control surface for the map**

- **What:** `assets/js/looper-map-bus.js` (new) exposing
  `window.LooperMapBus = { setCategory(cat), flyTo(lng, lat, zoom?),
  fitCategory(cat, radiusM?), zoom(delta), reset(), showBusiness(idOrName),
  openNews(id) }` — thin wrappers around the existing map + marker systems.
  Voice router consumers, `askSwarm`'s `<map>` tag handler, gateway client
  actions (`map.search`), and F4.2 deep links ALL call the bus instead of
  poking `window.localloopMap` directly.
- **Why:** today three code paths each drive the map their own way; the bus
  makes voice/bot control testable and stops regressions.
- **Acceptance:** every bus method callable from DevTools console with
  visible effect; askSwarm suburb flyTo still works (now via bus); unit
  smoke test with a mocked map object.
- **Depends:** F3.2 (can land together).

# 05 — Phase 4 — Jarvis: Ricky ↔ the ecosystem

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F4.1** — Ricky gets LocalLoop tools
- [ ] **F4.2** — Map deep links (`?cat=…&q=…&fly=lng,lat,zoom`)
- [ ] **F4.3** — Ricky bridge-ops cockpit (read-only v1)

> **2026-07-12 progress (see `.SEED/decisions.md`):** F4.1 tools
> (localloop_search/businesses/open_map/bridge_status) + LocalLoop persona
> shipped in `looper-bot/electron/main.cjs`; F4.2 map-side deep-link parsing
> shipped in `web/jarvis/looper-jarvis.js` (verified headless) and the
> desktop side builds the same URLs; F4.3's backend read path
> `GET /api/ingest/status` shipped. Boxes tick after Bill's manual voice
> acceptance ("what's good for lunch in Bondi?") and, for F4.2, once llx11
> embeds the Jarvis layer.

---


---

**F4.1 — Ricky gets LocalLoop tools**

- **What:** Add model-facing tools to `looper-bot/electron/main.cjs`
  `toolSpecs` + `tools:execute`: `localloop_search` (GET
  `{LOOPER_API_BASE}/api/search`), `localloop_discover` (F2.3),
  `localloop_archetype_skills` (F2.4), `localloop_pins` (GET /api/pins),
  `localloop_gateway_health` (GET gateway `/health`), each returning an
  artifact (table/markdown) for the ArtifactPanel. Add `LOOPER_API_BASE` to
  `.env.local` handling (default `http://localhost:8000`).
  Update `RICKY_INSTRUCTIONS` so Ricky knows: it is LOOPER's desktop face;
  anti-bias rules; when asked about local businesses it MUST use the tools,
  present multiple options, and never invent ratings.
- **Acceptance:** ask Ricky "what's good for lunch in Bondi?" → it calls
  `localloop_search`, artifact panel shows an options table with ⭐ counts,
  voice answer names ≥2 options; tools fail gracefully offline.
- **Depends:** F0.2 (backend running); better after F2.3/F2.4.

---

**F4.2 — Map deep links (`?cat=…&q=…&fly=lng,lat,zoom`)**

- **What:** llx11 `index.html` parses query params on load and routes them
  through `LooperMapBus` (category filter, search query into the Looper
  dock, camera). Ricky gets tool `localloop_open_map` that builds the URL
  and opens the browser (`open` on macOS).
- **Acceptance:** `https://localloop.ai/?cat=Food&fly=151.2743,-33.8908,16`
  opens filtered + positioned; Ricky "show me Bondi cafés on the map" opens
  exactly that URL.
- **Depends:** F3.4.

---

**F4.3 — Ricky bridge-ops cockpit (read-only v1)**

- **What:** Tools for Bill to ask "how's the bridge?": `bridge_status`
  (reads looper `GET /api/ingest/status` — add tiny endpoint returning last
  20 `bridge_events` + counts by status), `pending_pins` (Supabase count of
  hybridcard pins pending review, via gateway `GET /api/bot/map/pins?...`
  read-only path if enabled, else via looper proxy). NO write tools yet —
  writes wait for the gateway's Phase 18B approval flow.
- **Acceptance:** "Ricky, any card deals waiting for approval?" → correct
  count + table artifact; all calls read-only (verified by gateway audit
  log / code review).
- **Depends:** F1.5.

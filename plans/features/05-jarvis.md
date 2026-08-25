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
>
> **2026-08-12 update:** llx11 embedding is confirmed complete and merged via
> PR #75 at `158299a` with every remote gate green (script order, bus binding,
> deep-link handler, listening-state sync, install/secret scan, unit/integration,
> Playwright E2E, and `ci-required`). F4.2 now waits only for its dedicated
> direct-contract test + Bill's live deep-link voice smoke. F4.1 still needs Bill's manual
> desktop voice acceptance. F4.3 is still partial: Looper has bridge status,
> but the pending-pin count/table artifact through the read-only gateway and
> its audit proof remain unimplemented/unverified. No write tools are allowed.
>
> **2026-08-12 wrap-up assessment:** F4.1 is also not yet checkbox-complete:
> `localloop_search`, `localloop_discover`, `localloop_businesses`, open-map,
> and bridge-status exist, but the planned `localloop_pins` and
> `localloop_gateway_health` desktop tools do not; archetype-skills depends on
> unfinished F2.4. The gateway health URL is live/read-only, but no new tool was
> started during wrap-up. LocalLoop confirmed F4.3 is cross-repo blocked:
> llx11 has no supported machine-authenticated pending-pin GET endpoint, schema,
> pagination/filter contract, or read-audit semantics. Its admin browser's
> direct Supabase query must not be copied into Looper. Resume from these exact
> gaps after compaction; keep all F4 checkboxes open.
>
> **2026-08-12 sanctioned F4.3 client slice:** coordinator unblocked Looper
> against LocalLoop SPEC-055. `localloop_pending_pins` now calls only
> `GET ${LOCALLOOP_GATEWAY_URL}/api/bot/map/pins` with fixed
> `source=hybridcard&status=pending_review`, bounded page/limit, and
> `Authorization: Bearer ${LOOPER_BOT_READ_TOKEN}` from Electron main.
> Responses are strict-allowlisted, pagination-bound, rendered as an exact
> count/table artifact, and fail closed on auth/backend/select/audit failures;
> redirects, insecure non-loopback HTTP bases, unsafe card links, raw payload,
> and unrecognized keys are rejected/removed. `localloop_gateway_health` also
> shipped. Fifteen Node contract/security tests, typecheck, build, and live
> public health read are green. LocalLoop provider branch `cd4c751` (core
> `71c3052`, hardening `af31947`) subsequently merged through PR #80 to main
> at `d77ccf8659638f71ee39f813691ecd597d1aa0d3`; all remote gates passed and
> issue #78 closed. Gates 1–2 + Worker deploy + HTTP-layer proof were
> **activated 2026-08-22** under owner direction: audit migration applied,
> shared token provisioned in Worker + Looper, Worker deployed (version
> `0fb82412`), and a live audited 200 proven by a direct endpoint probe (audit
> row `12957da6`, `action pin_pending_list_read`). Gate 3 is only PARTIAL — the
> `localloop_pending_pins` tool has NOT been invoked through Electron. Keep F4.3
> unchecked until the direct-tool invocation (gate 3) + voice acceptance
> (gate 4) are completed; the HTTP probe does not establish them.

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

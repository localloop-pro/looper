# F3/F4 Jarvis map layer — build evidence (2026-07-12)

- `jarvis-dock-smoke.png` — headless Chromium screenshot of the Jarvis dock:
  animated Looper face, options panel for "find me a cafe near me" with
  community ratings + "View card →" (HybridCard) link.
- Produced by `web/tests/jarvis-smoke.playwright.js` against
  `web/tests/jarvis-harness.html` (fake map + stubbed API — no mic/CDN/backend).
- Verified in that run: grammar routing (Food, radius 1000 from "near me"),
  /api/search call shape, fitBounds padding 50 / maxZoom 15, suburb flyTo,
  zoom in, reset, deep links (?cat=Food&fly=151.2743,-33.8908,16), zero
  console errors. Router grammar: 46/46 unit tests
  (`node web/tests/voice-command-router.test.js`).
- NOT verified here (network-blocked build env): backend pytest, looper-bot
  typecheck/build, real-mic voice, live map tiles. Run those per README.

# .SEED/gotchas.md — mistakes to never repeat

- BRIDGE-CONTRACT-v1 payloads are FROZEN. Receivers verify HMAC over the RAW
  body (`timestamp + "." + body`, constant-time compare, ±5-min window) and
  upsert idempotently on `eventId`. The sender retries ALL non-2xx (even 4xx)
  — receivers must be replay-tolerant.
- `rank_boost: false` anti-bias invariant: never rank by discount, source, or
  payment. Reviews + recency + proximity only.
- `deal.removed` / `active:false` means DEACTIVATE the pin/business — never
  hard-delete.
- The old voice build has a stale-closure bug (radius updates lag one
  command) — port the fix, not the bug. `includes("stop")` substring match
  misfires on "bus stop" — use word boundaries.
- Web Speech API needs HTTPS (or localhost), works in Chrome/Edge/Safari,
  NOT Firefox — always feature-detect and fall back to typing.
- looper `README.md` mentions files that don't exist yet
  (`backend/services/review.py`, `matching.py`, `hermes/`,
  `training/finetune.py`) — trust the file tree, not the README.
- looper-bot uses OpenAI Realtime endpoints/models configured in
  `electron/main.cjs` — confirm current model names against OpenAI docs at
  build time before changing.
- llx11 `index.html` is a ~517KB monolith — make surgical, additive edits;
  never regenerate the whole file.
- Backend search is accent-sensitive: seeded categories use "café", so
  `q=cafe` returns 0 results while `q=café` works. Voice transcripts and
  widget users will type "cafe" — normalize accents when F3.x lands.
- On Bill's machine a local TypeDB server already listens on port 8000 —
  run the backend with `LOOPER_PORT=8010` locally (README documents this).
- `wrangler dev` on Bill's machine: the local workerd binary supports max
  compatibility date 2026-05-28, but wrangler.jsonc pins 2026-06-05 — local
  dev needs `--compatibility-date 2026-05-28` (deploys are unaffected).
- llx11 on localhost is ALWAYS test mode (`test-mode.js`): `LocalLoopAPI`
  only initializes when the supabase-js CDN script loads; embedded/preview
  browsers may fail its SRI fetch — verify real-data map behaviour in a
  normal browser (or on staging), not headless previews.
- llx11 browser code cannot read the `pin.coordinates` geography column:
  PostgREST returns it as WKB hex, `LocalLoopAPI.parsePinCoordinates` is
  referenced but NEVER DEFINED anywhere, and the site's marker modules rely
  on `payload.lat`/`payload.lng` instead (claim-V1 convention). Anything that
  writes pins for the map MUST duplicate lat/lng into the payload (the bridge
  receiver does since F1.4); hybridcard-markers.js also carries a WKB-hex
  fallback parser.
- llx11 `pin` table: trigger `trg_pin_computed_columns` recomputes
  `expires_at`/`is_expired` from `created_at + heartbeat_duration` on EVERY
  insert AND update — PATCHing `expires_at` directly is silently clobbered.
  To expire a pin, set `heartbeat_duration` to `'0 hours'`. Also means a
  1-hour-heartbeat draft dies before moderation — bridge pins use `1 month`.
- Coolify at `167.86.79.151:8000`: password in `secrets/looper-coolify.env`
  was rejected (2026-07-21) for several emails including `dev@localloop.pro`
  and `bminglis@icloud.com` — reset before assuming Coolify deploys work.
- `backend/.dockerignore` must NOT exclude `Dockerfile` — Railway/Coolify
  uploads fail silently if the Dockerfile is omitted from context.
- Cloudflare quick tunnels (`*.trycloudflare.com`) change hostname on every
  restart — update Worker `ORIGIN` var (`wrangler deploy` in
  `workers/looper-api-proxy`) whenever the tunnel is recreated.
- urllib/python default UA gets Cloudflare 1010 on `looper.localloop.ai`;
  use curl with a browser User-Agent for pin smoke tests.
- CF Worker `looper-api` must be re-deployed (`npx wrangler deploy` in
  `workers/looper-api-proxy/`) whenever the `ORIGIN` env var changes in
  `wrangler.toml`. Without a re-deploy, Cloudflare falls through to the raw
  DNS record (which may be an expired tunnel CNAME) instead of invoking the
  Worker — manifests as CF Error 1016 on `api.localloop.ai`.

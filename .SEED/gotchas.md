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

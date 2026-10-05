---
name: localloop-search
form: mcp
archetype: platform
home_repo: looper
path: backend/routes/search.py
status: candidate
owner_floor: looper
risk: high
why: Three floors each re-implement find-local-options against the Looper API; one MCP lookup tool would return the API's own order behind auth and limits.
---

# localloop-search (inventory top-5 #2)

One MCP server with three lookup tools over the Looper API: `search`,
`discover` and `businesses`. Inventory rows C1 and A14
(`docs/skills/INVENTORY.md`, looper#72).

Pinned: looper @ `9becb9c` · map @ `13400a8` · cards @ `7a0e584`

## Evidence

- The API: looper `backend/routes/search.py:60` (`GET /search`),
  looper `backend/routes/search.py:232` (`GET /businesses`),
  looper `backend/routes/discover.py:251` (`GET /discover`).
- Already wrapped as desktop tools in looper-bot: tool definitions
  looper `looper-bot/electron/main.cjs:169`, looper `looper-bot/electron/main.cjs:186`,
  looper `looper-bot/electron/main.cjs:202`; wrappers
  looper `looper-bot/electron/main.cjs:1161`, looper `looper-bot/electron/main.cjs:1186`,
  looper `looper-bot/electron/main.cjs:1213`.
- The map's gateway exposes a chat tool that would call it:
  map `workers/looper-gateway/src/index.mjs:85` (`looper_chat`).
- Public reads already sit behind looper's edge limits:
  looper `backend/services/edge_boundary.py:172` (`PublicReadBoundary`).

## Rules for whoever builds it

- Return the API's results **in the API's order**. Never re-rank, filter by
  paid status or set `rank_boost` (AGENTS.md rule 1).
- Auth plus per-IP / per-key rate limits before it is reachable by anything
  but the owner's own desktop.
- Read-only tools only. The looper-bot write tools (`records_*`,
  `computer_*`) never go over MCP.

## Shared with

- looper (home): looper-bot desktop tools would call the MCP tools instead of
  their own wrappers.
- localloop.pro-main: the gateway's `looper_chat`.
- hybridcard-v2: a possible consumer (e.g. the Scout employee). Scout does not
  call Looper today; it reads public pages.

## Why risk `high`

Matches inventory row C1 (HIGH). The handlers are reads, but every `/search`
and `/discover` call commits a PII-scrubbed `training_log` row:
looper `backend/services/telemetry.py:33` to looper `backend/services/telemetry.py:39`,
called at looper `backend/routes/search.py:219`,
looper `backend/routes/discover.py:236` and looper `backend/routes/discover.py:353`.
Those rows are exported for fine-tuning by looper `training/export.py:11`.
`/businesses` writes nothing. The owner decides whether agent traffic belongs
in the training log at all (or gets a telemetry opt-out) before this moves
past `candidate`.

# #86 — /health carries the deployed commit (2026-10-03)

`GET /health` adds `"commit"`: the first 12 chars of `LOOPER_COMMIT`, else of
Coolify's runtime `SOURCE_COMMIT`, lower-cased, and `""` unless that is hex.
Existing keys and the 200 status stay; no new endpoint, no auth change.

`backend/Dockerfile` declares `ARG SOURCE_COMMIT=""` and sets
`ENV LOOPER_COMMIT=$SOURCE_COMMIT` after the pip installs, so a new commit only
rebuilds the final copy layers. The runtime `SOURCE_COMMIT` fallback exists
because Coolify injects it into the container even with the build option off
(Coolify docs, checked via Context7 on 2026-10-03); the build-time value wins.

`scripts/loop_check.py` appends `commit <sha>` (or `commit unknown`) to its
existing health line, so its output stays one line per check and GET-only.
The owner steps are in `docs/BACKEND-COMMIT-MARKER.md`. The map site's empty
`commit` (BLIND-SPOTS §3.4) lives in localloop.pro-main and is out of scope.

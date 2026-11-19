# #152 — A silent fallback hides a broken dependency (2026-11-20)

`/api/discover` caught every TypeDB graph error with a bare
`except Exception:` and served the SQLite fallback with no log line. The
response said `"engine": "fallback"`, but nobody could see why, so a broken
TypeDB connection would go unnoticed in production.

Lessons:
- A transparent fallback still needs one log line. Log a single WARNING on
  `looper.discover` with the exception class and message, then fall back as
  before. The response shape stays the same, so callers see no change.
- Log the class and message only: no traceback, no suburb, no coordinates.
  Mask `TYPEDB_ADDRESS` in the message in case the driver echoes it, and cut
  the message at 200 characters.
- Test it with `caplog` and a monkeypatched `_graph_discover` that raises. No
  live TypeDB is needed.
- A fresh worktree has no `backend/data/`, so the test DB can't open
  (`unable to open database file`). Run `mkdir -p backend/data` first.

# #152 — A silent fallback hides a broken dependency (2026-11-20)

`/api/discover` caught every TypeDB graph error with a bare
`except Exception:` and served the SQLite fallback with no log line. The
response said `"engine": "fallback"`, but nobody could see why, so a broken
TypeDB connection would go unnoticed in production.

Lessons:
- A transparent fallback still needs one log line. Log a single WARNING on
  `looper.discover`, then fall back as before. The response shape stays the
  same, so callers see no change.
- Never log `str(exc)` from a broad `except`. The catch covers the TypeDB
  driver and SQLAlchemy queries, and their messages can carry request values
  (category, coordinates), SQL parameters, host:port, URL credentials or
  injected newlines. Masking the one configured address and truncating is not
  enough: a review showed partial addresses, IPs and `password=` pairs still
  got through.
- Use an allowlist instead: log the exception class plus only details proven
  safe (a fixed string raised in our own code, a `[CXN01]`-style TypeDB code,
  a SQLAlchemy error code, a missing module name). Everything else becomes
  "message withheld". The class name alone usually says what broke.
- Prove privacy with adversarial tests: feed messages full of request values
  and secret-like strings and assert none of them reach the log. A benign
  test message only proves that a warning is written.
- A fresh worktree has no `backend/data/`, so the test DB can't open
  (`unable to open database file`). Run `mkdir -p backend/data` first.

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
- Don't swing to the other extreme either. A second review rejected
  "message withheld" for ordinary errors: the operator can't tell two
  `RuntimeError`s apart. Scrub word by word instead
  (`_graph_failure_summary`). Plain words and `[CXN01]`-style TypeDB codes
  survive. Tokens with digits or symbols (coordinates, ports, IPs, URLs,
  `key=value`), the caller's own suburb/category words, TypeDB address labels,
  credential keywords and the word after them become `[redacted]`. For
  SQLAlchemy errors, log only the driver's own message (`exc.orig`), never the
  statement or its parameters.
- Test both sides: adversarial messages full of request values and
  secret-like strings must not reach the log, and benign messages
  ("typedb connection refused", "database is locked") must survive word for
  word.
- A fresh worktree has no `backend/data/`, so the test DB can't open
  (`unable to open database file`). Run `mkdir -p backend/data` first.

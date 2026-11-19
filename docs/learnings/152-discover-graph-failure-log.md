# #152 — A silent fallback hides a broken dependency (2026-11-20)

`/api/discover` caught every TypeDB graph error with a bare
`except Exception:` and served the SQLite fallback with no log line. The
response said `"engine": "fallback"`, but nobody could see why, so a broken
TypeDB connection would go unnoticed in production.

Lessons:
- A transparent fallback still needs one log line. Log a single WARNING on
  `looper.discover`, then fall back as before. The response shape stays the
  same, so callers see no change.
- Never log exception message text from a broad `except`. The catch covers
  the TypeDB driver and SQLAlchemy queries, and their messages can carry
  request values (suburb, category, coordinates), SQL parameters, host:port,
  URL credentials, street addresses or injected newlines.
- Don't try to scrub free text. This PR tried masking the address, then a
  word-by-word scrubber (plain words kept; digits, symbols, request words and
  credential keywords redacted). Three review rounds still found leaks:
  `authentication failed for password is hunter` logged
  `... [redacted] hunter`, and `failed for address 25 Ocean Street` logged
  `... [redacted] Ocean Street`. Plain words can be secrets or addresses, and
  no rule list can tell.
- So log only what the code controls: the exception class name (checked
  against a strict identifier regex) and, for `typedb.*` exceptions, a
  `[XXX00]` error code matched strictly at the start of the message. Nothing
  else: no message, no traceback, no request values, no `TYPEDB_ADDRESS`.
  Example: `discover graph engine failed, using fallback:
  typedb.common.exception.TypeDBDriverException [CXN01]`.
- This deliberately drops useful diagnostics: "connection refused" and
  "database is locked" both log only their class. That is the price of a
  log that can't leak. To find the detail, reproduce with the same
  `TYPEDB_ADDRESS` locally, or look up the TypeDB code.
- Tests assert the exact log line, not a list of forbidden words, so any
  extra text fails the test.
- A fresh worktree has no `backend/data/`, so the test DB can't open
  (`unable to open database file`). Run `mkdir -p backend/data` first.

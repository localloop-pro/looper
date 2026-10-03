- looper#68: a report over a SQLite file opens it with `file:...?mode=ro`
  (writes refused, missing file never created) and the test proves it by
  comparing the file's bytes and the folder listing before and after. Compare
  timestamps with `datetime(col)` on both sides, not raw strings: SQLAlchemy
  writes `YYYY-MM-DD HH:MM:SS.ffffff`, hand-written rows may use `T`.
  Free text from users is only reported when it repeats (>= 2) and gets
  `scrub_pii()` again on output, because old rows may predate the scrubber.

- PR #77 round 1: treat metadata labels as free text too. An intent can be
  an email, mobile or a person's name. Classify into fixed categories and
  group after classification; redacting only query text is insufficient.
- SQLite's built-in `lower()` is ASCII-only. Use Python Unicode lowercasing
  through a connection-local function for report grouping. Keep the original
  repeated-query threshold and output redaction.
- A shared helper is not stdlib-only if its module imports the ORM. Extract
  pure redaction into its own module and test `python -S` on help, text and
  JSON output, as well as API-to-backup-to-report behavior.

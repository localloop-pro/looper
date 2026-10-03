- looper#68: a report over a SQLite file opens it with `file:...?mode=ro`
  (writes refused, missing file never created) and the test proves it by
  comparing the file's bytes and the folder listing before and after. Compare
  timestamps with `datetime(col)` on both sides, not raw strings: SQLAlchemy
  writes `YYYY-MM-DD HH:MM:SS.ffffff`, hand-written rows may use `T`.
  Free text from users is only reported when it repeats (>= 2) and gets
  `scrub_pii()` again on output, because old rows may predate the scrubber.

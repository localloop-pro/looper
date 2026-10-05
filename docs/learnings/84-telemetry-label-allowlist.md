# 84 — Allow-list telemetry labels, don't just scrub free text

`scrub_pii` only ran on `query_text` / `response_text`. `intent` and `session`
are public query params on `/api/search` and `/api/discover`, so a caller could
put an email or mobile in them and it landed verbatim in `training_log` (and in
the fine-tune export and weekly report).

Lesson: any field a caller can set is free text, even if it is "just a label".
For labels, validate the *shape* (short slug / opaque id) and replace anything
else (`"other"` / NULL) instead of trying to regex out every kind of PII.
Use `re.fullmatch`, not `^…$` — `$` lets a trailing newline through.

Older rows written before this fix may still hold such values; cleanup is the
owner's call.

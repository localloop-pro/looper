# #73 — One widened search pass when nothing is in range (2026-10-03)

`GET /api/search` with `lat`/`lng` that finds 0 results inside `radius_km`
filters the same text-matching candidates once more with
`LOOPER_SEARCH_FALLBACK_KM`. The default is 10, it is read once at startup,
and invalid or non-positive values fall back to 10. If `radius_km` is
already at least that wide, no second pass runs. The response gains the
optional `widened_to_km` field (`null` when no widened pass ran). Callers
that read only `results`/`message` are unaffected
(docs/CROSS-REPO-CONTRACTS.md).

The ranking is unchanged in both passes: relevance, then review_count, then
distance. No new ranking inputs. Whether the sort should change is still an
owner decision (BLIND-SPOTS §4.7); this PR only makes the message describe
it truthfully ("best match first, then most community reviews, then
nearest").

Messages are plain text (#37), declare no "best", and never invite an action
that 403s while `LOOPER_PUBLIC_WRITES` is off. Empty answers read "No one's
listed for 'X' near here yet." (no location) or "... within 10 km yet."
(after the widened pass).

Rollback: revert the #73 PR. There is no schema or data change, and the
response field simply disappears again. To switch the widening off without
a revert, set `LOOPER_SEARCH_FALLBACK_KM` to a value no larger than the
callers' radius, e.g. `0.1`, and restart.

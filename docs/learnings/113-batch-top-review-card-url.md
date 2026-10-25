# #113 — Batch display-only review excerpts and card URLs

The review statistics batch did not remove all page-size-dependent SQL: each
returned search/discover row still loaded its top review and card URL
separately. Batch those display fields only after the frozen ranking has
selected the page, and make their implicit SQLite tie-breaks explicit
(`Review.created_at DESC, Review.id ASC`; `Deal.id ASC`) so fewer statements
cannot change response bytes.

Cache keys for public reads must sort the allowlisted `(name, value)` pairs.
The clients construct equivalent queries in different parameter orders; keeping
request order in the key silently prevents those answers from sharing the
opt-in cache. Values remain untouched because search echoes the original query.

Verify with the immutable read-path snapshot, explicit constant-SQL tests, the
bench ID dump diff, and a cache test that swaps parameter order. Rollback is a
normal revert of the #113 PR; there is no schema, data, dependency, ranking, or
deployment change.

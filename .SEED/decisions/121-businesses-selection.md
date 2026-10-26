# #121 — Eligible business selection before limiting (2026-10-26)

`GET /api/businesses` filters active/category candidates and known distances
before selecting a page. Rank all eligible candidates by public review count,
then full-precision distance, then ascending business ID (existing SQLite
insertion-order convention). Round distance only for the response. Zero is
valid; missing business coordinates remain included with null distance, after
known distances at equal review count. Partial caller coordinates still mean
no distance filter. No response fields or bridge contracts change.

Reuse review_stats batches of 500 eligible IDs; no per-business SQL. Correct
selection requires reading all matching candidates: O(N) memory and O(N log N)
sorting, unlike the old incorrect limited scan. A future SQL/geospatial
optimization needs its own measured issue; no schema/index changes here.

Rollback: revert this PR; no data repair or migration is required.

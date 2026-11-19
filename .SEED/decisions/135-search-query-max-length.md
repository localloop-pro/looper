# 135 — Cap the search query length at the public boundary

Decision (2026-11-19): `GET /api/search` declares `q` with `max_length=200`
next to `min_length=1`. A longer `q` gets FastAPI's normal 422 before the
route body runs. The limit is 200 characters, well above any real Jarvis or
widget query.

Why: `q` was split into tokens and each token became OR'd LIKE clauses, so
one unauthenticated request with a ~12 KB multi-word query built a very large
SQL expression. The check sits at the Query boundary so tokenizing, ranking
and response shapes do not change. Queries of 200 characters or less behave
exactly as before.

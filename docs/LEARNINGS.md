# LEARNINGS.md — one short lesson per merged PR

- looper#27: guard unauthenticated writes with a per-route FastAPI dependency
  (`dependencies=[Depends(...)]`) so an empty body gets 403 instead of 422, and
  delete leaky reads outright rather than putting them behind the same flag.
  Also: never name a zsh loop variable `path` — it is tied to `$PATH`.
- looper#30: measure statements, not just milliseconds — `/api/discover` ran
  ~2,300 SQL queries per request (3 review lookups per candidate business),
  but cursor time was only 24 ms of 265 ms; the rest was SQLAlchemy overhead
  per statement. One `GROUP BY` per 500 ids fixed it. Record a snapshot of
  the full responses on the old code BEFORE refactoring, so "same results"
  is a test, not a claim.

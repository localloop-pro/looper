# #30 — Count SQL statements, not just milliseconds (2026-10-02)

`/api/discover` ran ~2,300 SQL queries per request (3 review lookups per
candidate business), but cursor time was only 24 ms of 265 ms; the rest was
SQLAlchemy overhead per statement. One `GROUP BY` per 500 ids fixed it.
Record a snapshot of the full responses on the old code BEFORE refactoring,
so "same results" is a test, not a claim — and re-record it on main's
unchanged routes when main's behaviour moves under you.

# 133 — Public review reads show one label, never a reviewer's first name

Decision (2026-11-19): `GET /api/reviews/{business_id}` returns
`"reviewer": "Community member"` for every review. The response key, key
order and shape are unchanged. The `User` lookup on this read is removed.

Why: the Facebook import stores a real group member's author name in
`User.first_name`, and reviews default to `is_public`. An unauthenticated GET
therefore published real first names. Vision rule: no names leave the system.
The fix is on the read response only. Stored data and the import pipeline are
unchanged; this is a stopgap for the read path, not a data cleanup.

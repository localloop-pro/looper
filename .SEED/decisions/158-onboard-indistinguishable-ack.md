# 158 — POST /api/onboard returns the same ack for new and existing mobiles

Decision (2026-11-24): `POST /api/onboard` always answers HTTP 200 with
`{"message": "<fixed ack>"}`. The body never includes `user_id`, `join_code`, or
`first_name`. A new row is created only when the mobile is not already stored;
repeat posts create no duplicate user. Both code paths call `generate_join_code`
(DB uniqueness probes) before returning the same ack. Join codes stay in SQLite
for the owner-side delivery path (manual / future loop-onboard); this route does
not send SMS and does not change that path.

Why: 409 vs 200 let anyone enumerate registered mobiles. The vision asks for
public-safe payloads before public writes go on. A fixed ack closes registration
oracle without leaking credentials in HTTP.

Rollback: revert `backend/routes/users.py` and `backend/schemas.py`, restore
`OnboardUserResponse` with `user_id` / `first_name` / `join_code`, and bring
back the 409 branch for duplicate mobiles.
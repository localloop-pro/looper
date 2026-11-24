# 158 — POST /api/onboard returns the same ack for new and existing mobiles

Decision (2026-11-24): `POST /api/onboard` always answers HTTP 200 with
`{"message": "<fixed ack>"}`. The body never includes `user_id`, `join_code`, or
`first_name`. A new row is created only when the mobile is not already stored;
repeat posts create no duplicate user. Both code paths call `generate_join_code`
(DB uniqueness probes) before returning the same ack.

**Join-code delivery (Twilio SMS, Bill 2026-11-24):** After the HTTP response,
a background task (`services/onboard_sms.py`) may send the stored join code by
SMS via Twilio's Messaging REST API. Credentials come only from env
(`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` or `TWILIO_API_KEY_SID` /
`TWILIO_API_KEY_SECRET`, plus `TWILIO_FROM_NUMBER` or
`TWILIO_MESSAGING_SERVICE_SID`). If Twilio is not configured, log a generic
warning (no mobile, no code) and skip send. **Existing mobiles:** re-send the
stored join code when the per-number rate limit allows (default 3 per hour);
**new mobiles:** send the code just written. Same background hook on every
onboard so HTTP timing does not reveal new vs existing. The HTTP body never
contains the code.

Why: 409 vs 200 let anyone enumerate registered mobiles. SMS keeps delivery
off the wire while legitimate users (new or re-requesting) get their code when
Twilio is enabled.

Rollback: remove `services/onboard_sms.py` and Twilio env from README;
revert `users.py` to ack-only; or full rollback per first paragraph to restore
409 and inline join_code in JSON.
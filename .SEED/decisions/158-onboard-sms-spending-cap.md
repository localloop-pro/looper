# 158 — Onboard SMS spending cap (daily + durable per-number limit)

Decision (2026-11-24): Before enabling `LOOPER_PUBLIC_WRITES`, onboard join-code
SMS must not exhaust Twilio budget. `services/onboard_sms.py` enforces:

- **Global daily cap:** `LOOPER_SMS_DAILY_CAP` (default **200**), UTC calendar
  day, all numbers combined. When at cap, log `onboard SMS skipped: daily cap`
  (no mobile, no code) and skip send; HTTP 200 ack unchanged.
- **Per-number cap:** still **3 sends per rolling 60 minutes** (not clock-aligned
  hour), keyed by **SHA-256** of `salt:mobile` (`LOOPER_SMS_RATE_SALT` or a
  built-in default).
- **Durability:** both caps use SQLite table `onboard_sms_sends` (migration
  `backend/migrations/001_onboard_sms_sends.sql`, applied by `init_db()`).

Why: in-memory limits reset on worker restart and do not share across processes;
daily cap prevents runaway cost if public writes are flipped on.

Rollback: set `LOOPER_SMS_DAILY_CAP=0` to block sends, or revert this change and
drop table `onboard_sms_sends` on production if needed.
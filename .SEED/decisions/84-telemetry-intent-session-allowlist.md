# looper#84 — telemetry stores only safe `intent` / `session_id` shapes

- `intent` is stored lower-cased only if it matches `^[a-z][a-z0-9_-]{0,31}$`,
  otherwise `"other"`. Known callers (`search`, `discover`, `business`,
  `voice`) are unchanged.
- `session_id` is stored only if it matches `^[A-Za-z0-9_-]{1,64}$` and
  contains no email or AU mobile (`EMAIL_RE` / `AU_MOBILE_RE`), otherwise NULL.
- Enforced in `backend/services/telemetry.py` (`clean_intent`,
  `clean_session_id`), so every `log_query` caller gets it.
- No schema change and no rewrite of old rows: older `training_log` rows may
  still hold such values. Cleanup is the owner's call.

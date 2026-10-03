# 84 — training_log stores only slug-shaped intent and opaque session ids

Decision (2026-10-03): `services/telemetry.log_query` stores
- `intent` lower-cased if it fully matches `[a-z][a-z0-9_-]{0,31}`, else
  `"other"`, NULL if missing;
- `session_id` as sent if it fully matches `[A-Za-z0-9_-]{1,64}` and contains
  no `EMAIL_RE` / `AU_MOBILE_RE` match, else NULL.

Why: both are caller-supplied public params; shape allow-listing is the only
reliable way to keep PII out of telemetry. Known callers (`search`,
`discover`, `business`, `voice`) are unchanged. No schema change, existing rows
untouched (cleanup is the owner's call). Ranking code is not touched.

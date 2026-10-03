- looper#84: scrubbing free text is not enough. Every caller-supplied field
  that reaches telemetry (here `intent` and `session`) needs a shape
  allowlist: keep a short slug or an opaque id, replace anything else with
  `"other"` / NULL. Fix storage, not the report that reads it, because
  `training/export.py` ships the rows too.

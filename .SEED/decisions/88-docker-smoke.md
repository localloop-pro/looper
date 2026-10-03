# #88 — Production image is a required CI gate

Issue #88 authorizes adding CI coverage; it does not authorize deployment.
Build `backend/Dockerfile` from the repo root with default args and exercise
the default CMD and HEALTHCHECK. Use a throwaway anonymous volume, no secrets,
TypeDB disabled, and a loopback-only port. Reuse existing action version pins
and `ci`'s `always()`/needs-result aggregation. Preserve every existing job and
the workflow's read-only permissions and secret-scanning rules.

Plan status: implementation prepared; host backend/web/Worker/bot checks pass.
Docker daemon unavailable locally; container acceptance, failure demonstration,
runtime and independent QA remain pending in the PR. No Featured spec/todo/db
exists in this repository; issue #88 and these per-issue documents track scope.
The production go-live checklist remains owner-gated and unchecked.

Validation exposed missing telemetry imports on main (PR #87). Restore only
the imports required by the existing sanitizer; no auth, data or API contract
change. Existing backend tests cover the corrected code.

Next: obtain hosted Docker evidence, confirm runtime, demonstrate broken-CMD
failure, then QA. #86/#76 were still open; recheck before acceptance. Rollback:
remove the job and `ci.needs` entry. Non-root USER remains a separate,
owner-approved volume migration; see the lesson's run/verify instructions.

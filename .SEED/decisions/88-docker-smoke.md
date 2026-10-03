# #88 — Production image is a required CI gate

Issue #88 authorizes adding CI coverage; it does not authorize deployment.
Build `backend/Dockerfile` from the repo root with default args and exercise
the default CMD and HEALTHCHECK. Use a throwaway anonymous volume, no secrets,
TypeDB disabled, and a loopback-only port. Reuse existing action version pins
and `ci`'s `always()`/needs-result aggregation. Preserve every existing job and
the workflow's read-only permissions and secret-scanning rules.

Plan status: implementation and local/hosted validation complete; QA pending.
Docker daemon unavailable locally; hosted run 37094224602 passed all checks,
including production image probes (Docker job 32s, smoke 6s). Throwaway broken
CMD commit 285ade4 failed Docker smoke and aggregate ci in run 37094131435;
reverted by ca9aead, which passed. No Featured spec/todo/db
exists in this repository; issue #88 and these per-issue documents track scope.
The production go-live checklist remains owner-gated and unchecked.

Validation exposed missing telemetry imports on main (PR #87). Restore only
the imports required by the existing sanitizer; no auth, data or API contract
change. Existing backend tests cover the corrected code.

Next: independent QA and final-branch CI. #76 landed during validation; merge
main into the published branch (no force-push) and retain both required smoke
jobs. #86 remains open; add its commit contract only once merged. Rollback:
remove the job and `ci.needs` entry. Non-root USER remains a separate,
owner-approved volume migration; see the lesson's run/verify instructions.

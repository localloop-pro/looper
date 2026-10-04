# #96 — Make failed main CI visible as one issue (2026-10-03)

Keep all existing gates and the aggregate `ci` job unchanged. Add a main-push
reporting job after every gate and `ci`, with `always()` so failures reach it.
Issue #96 authorizes the sole exception to the workflow's write-scope ban:
`issues: write` only on this job, plus read-only contents/PR lookup scopes.
Use the existing GITHUB_TOKEN via gh, with JSON stdin rather than shell payloads.

A stdlib pure function selects open/comment/close/nothing. All gates must
succeed to close; cancelled/skipped/empty results never prove recovery.
Serialize monitor jobs, paginate exact-title open-issue lookup (exclude PRs),
and ignore superseded main commits. Assume humans reserve `main is red` for
the monitor; GitHub issue creation has no atomic unique-title API. API errors
fail reporting; they cannot make the required gate pass. No new secrets,
application behavior changes, deployments or customer data access.

Tests run on both PR and main in the existing backend job. Dry runs never
contact GitHub. See docs/MAIN-RED-RUNBOOK.md for commands and rollback.
The Featured spec/todo/done stores are absent here; #96, its PR, STATUS.md and
these per-issue records track implementation. QA/hosted checks and real
main-push reporting remain acceptance steps after submission/merge.

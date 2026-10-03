# #101 — Refresh status from GitHub, separate merge from deploy (2026-10-03)

Check every issue/PR reference against GitHub on the update day, including
cross-repo blockers. Closed issues can still describe unresolved owner gates;
merged application code does not prove the running image includes it.

Copy the health-line example from BACKEND-COMMIT-MARKER.md and check it against
scripts/loop_check.py. An unknown marker is not proof that Coolify's option is
off: runtime SOURCE_COMMIT can supply the marker independently. Link the owner
runbook and keep production verification explicitly owner-run.

Tracking: the Featured spec/todo/done files are absent. Issue #101, STATUS.md
and its PR track this docs-only cycle; no separate decision file is added
because the issue permits only STATUS.md and one lesson. Next: QA and CI,
then Bill's Monday 2026-10-05 checks. Rollback: revert this docs commit through
a reviewed PR; no service or data change is needed.

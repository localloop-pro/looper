# #69 — Status needs evidence and a deployment boundary (2026-10-03)

Conflicting historical trackers made implemented features look absent and
owner gates look complete. Keep one short `STATUS.md`, reviewed every Monday,
and preserve superseded documents as clearly marked archives.

A merged PR proves repository work, not production deployment. For example,
#27 / PR #33 closes public writes by default and deletes profile reads; the
lockdown tests prove that behavior locally. The E6 row must record that code
fix while leaving deployed behavior unverified until the owner's probe.

Check open PR state too: #28 / PR #47 is proposed, not merged at this update.
Link weekly measurement to #68 rather than inventing numbers. No production
probe or deploy is needed for a docs-only consolidation.

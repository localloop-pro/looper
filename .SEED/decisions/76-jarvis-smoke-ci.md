# #76 — Jarvis browser smoke is a required CI dependency (2026-10-03)

Add `jarvis-smoke` to the aggregate `ci` gate without changing existing jobs.
Use a private test-only npm manifest with Playwright 1.63.0 locked exactly.
Cache npm downloads and Chromium by OS, architecture and lockfile hash;
always run `playwright install --with-deps chromium` so Linux libraries are
installed even when the browser cache hits. No secrets or extra permissions.

The Bash runner owns only its loopback HTTP server, polls the harness with a
bounded timeout and traps exit/signals to stop it. The smoke closes Chromium
in `finally`, reports unexpected exceptions as exit 1, and treats desktop and
mobile console/page errors as failures. The harness uses stubbed map/API data;
this gate does not certify microphone, live map copies or production services.

Assumption: issue #76 is the approved scope. The Featured spec/todo/database
are absent; use this issue, PR, and these per-issue records rather than creating
parallel trackers. Acceptance and hosted timing are recorded in the PR.
Rollback: revert the #76 commit through a reviewed PR; no deployment needed.

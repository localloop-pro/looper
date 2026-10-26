# #119 — Widget recovery (2026-10-26)

At base 41b6c8cc481dcc331f05ea035dcc56c2286602ab, a local browser fixture
replaced fetch with an indefinitely pending promise, then with resolved headers
and a pending json() promise. Submitting cafe left input/send disabled in both
cases after observation; there was no timer/cancellation in the original source.
No provider or production service was contacted.

A header-only timeout misses body stalls. Race the complete asynchronous work,
abort at the deadline, and keep all rendering outside that work: even a host
that ignores cancellation cannot publish a late result. Cleanup belongs in
finally. A delayed geolocation callback must not start a request after timeout.

## Verify locally

From the repository root (Node 20+ and Python 3):

```bash
npm ci --prefix web/tests
(cd web/tests && npx playwright install chromium)
bash web/tests/run-jarvis-smoke.sh
```

The existing CI smoke runner now also runs widget recovery tests using its
local server, and cleans up on exit. For a standalone run, start
`python3 -m http.server 5369 --bind 127.0.0.1` in another terminal, then run
`node web/tests/widget-recovery.playwright.js`; stop the server with Ctrl-C.

The deterministic browser suite advances the real 15-second timer using the
Playwright clock, without adding a production timeout override. At 1280x720
and 390x844 it covers success, empty, HTTP errors, invalid JSON/schema, offline,
stalled headers/body, aborted signals, late completion during retry, successful
retry, stalled location, inert markup, keyboard access, overflow and console
errors. Both viewports passed. Existing Jarvis smoke, router/drift tests, Worker
24 tests, backend 770 passed/one TypeDB skip, and Electron typecheck/build/56
tests passed locally. Docker smoke was unavailable (daemon not running).
A manual mobile recovery screenshot was captured; the raw static server's
missing favicon emits a 404, intercepted in the isolated automated fixture.
Hosted CI and production acceptance are separate from this local evidence.

Security review: API content still uses textContent; no HTML injection, raw
error logging, new credentials, write routes, ranking or card-link changes.
The tests deliberately settle an aborted old request while retry is pending:
it neither unlocks controls nor writes stale text.

Rollback: revert this PR's commit and rerun the smoke command above. No data,
schema, environment or deployment changes. This restores the old unbounded
behavior, so prefer fixing forward. Next step is teammate QA and CI at the PR
head, followed by manager merge; no broader feature work is in this issue.

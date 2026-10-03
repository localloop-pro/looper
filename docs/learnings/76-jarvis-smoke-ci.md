# #76 — A browser smoke must fail and clean up (2026-10-03)

Logging page errors is useful only when it makes the required CI check fail.
A success-path `browser.close()` leaks the browser when a selector times out;
put it in `finally` and set `process.exitCode` after reporting the exception.
The shell that starts the HTTP server must trap exit and stop its own PID.
Chromium caching does not provide the Linux OS libraries: install them on
cache hits too. Keep the cache key tied to the pinned Playwright lockfile.

From the repo root, run the same smoke as CI:

```bash
(cd web/tests && npm ci && npx playwright install --with-deps chromium && npm run smoke)
```

Expected: face class, cafe options, View card link, deep-link checks,
`mobile dock fits 320px viewport: true`, `errors: none`, exit 0.
The runner stops port 8088 on both success and failure. A deliberately absent
face selector must report `Timeout 10000ms exceeded` and exit 1. Restore any
local fault before committing; the PR records the uncommitted failure proof.

This is a stubbed local harness, not live-map or real-microphone acceptance.
QA still verifies cross-repo copies and owner production checks separately.
Rollback: revert the #76 commit in a reviewed PR, then run the existing router,
drift and Worker tests; no service configuration or production data changes.

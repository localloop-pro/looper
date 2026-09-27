# Kaspa organization identity review — 2026-09-06

Scope: `main...9a89b3b` on `feat/kaspa-org-identity` (12 changed files).
The working tree was clean before the review. This review changes records only.

## Finding — P2: Expire verified wording independently of refresh completion

Location: `web/kaspa-identity.js:89–102`.

After the first successful response, `refresh(false)` leaves the old `fresh`
badge visible while awaiting `fetch()` and `response.json()`. Neither operation
has an application timeout, and the next poll is scheduled only after both
finish. A stalled API connection therefore keeps an expired identity looking
fresh and stops subsequent refreshes. The server's provider timeout does not
cover a stalled browser-to-API connection.

Browser reproduction (Playwright, intercepted fetch and controlled clock):

1. Mount a badge with a `fresh` response expiring in 60 seconds.
2. Leave the second fetch promise pending, simulating an unresponsive connection.
3. Advance the browser clock two minutes: two fetches have started and the badge
   still has `data-state="fresh"`.
4. Advance another two days: the badge still reads `Official · localloop.kas`
   with state `fresh`, and the request count remains two.

Required correction: remove fresh wording at `expiresAt` independently of
network completion, give the full refresh request a bounded timeout, and ensure
failed or timed-out requests still schedule retries. Include a browser regression
for a stalled refresh and recovery. Review status: **changes requested**; this
finding is open and no fix was implemented during the review.

## Validation

- `cd backend && .venv/bin/python -m pytest -q`: **107 passed, 1 skipped**.
  The skipped test requires an opt-in real TypeDB service. One existing
  Starlette/httpx deprecation warning was reported.
- Playwright: all four badge states (`fresh`, `stale`, `mismatch`,
  `unavailable`) rendered and retained the configured `qikflo.kas` scope.
- Playwright: stalled-refresh reproduction above confirmed the defect.
- `node --check web/kaspa-identity.js`: passed.
- `git diff --check main...HEAD`: passed.
- Adversarial review covered domain allowlisting, provider field matching,
  malformed responses, cache binding, tombstones, concurrency and badge expiry.
- Live KNS provider behavior and production deployment were not verified.
  Desktop build checks were not run because the desktop code is unchanged.

## Tracking and next action

`featured_webapp_SPEC.TXT`, `Featured_todo.md` and `Featured_done.db` are absent
from this checkout. The review is recorded in the existing Looper completion
tracker and linked from the master plan; no replacement tracker or completion
database was created. Next action: fix and retest badge expiry before accepting
this branch. No production changes were made.

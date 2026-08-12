# Looper completion status

Last verified: **2026-08-12**

This is the short operational tracker. The authoritative feature definitions
and checkboxes remain in `plans/features/` and `plans/IMPLEMENTATION_PLAN.md`.
Do not start untouched scope while an item below is waiting on its named gate.

## Verified green

- Backend: `80 passed, 1 skipped` (normal suite; TypeDB real-service test is opt-in).
- TypeDB acceptance: `1 passed` against Core 2.29.1 (signed ingest, located-in,
  graph/fallback parity); migration/seed/full-sync and down fallback also green.
- Looper desktop: `npm run typecheck` + `npm run build` green.
- Backend container: `docker compose config -q` + repo-root Docker build green.
- Jarvis router: node test green; LocalLoop reports 102/102 + PR E2E green.
- News audio worker: 4/4 isolated tests green.

## Existing work packages still open

| Package | Implemented/verified | Exact remaining gate |
|---|---|---|
| F1.5 bridge staging | outbox, both receivers, draft invisibility evidence | Bill: owner-approved approve/visible/remove cleanup and true staging proof |
| F2.1–F2.3 TypeDB | code + full local real-service acceptance complete | Bill: internal-only Coolify service, env, nightly task, repeat acceptance |
| F2.5 telemetry | search/discover logging + PII scrubbing tested | F2.4 archetype counters; do not begin unless that existing dependency is approved |
| F3.1–F3.4 voice/map | Looper code complete; llx11 wiring confirmed | LocalLoop direct tests for map bus + deep links; Bill Chrome mic/Firefox fallback review |
| F4.1–F4.2 desktop/deep links | tools/build and llx11 integration complete | Bill manual voice + live deep-link acceptance |
| F4.3 bridge cockpit | status read path exists | read-only pending-pin count/table artifact + gateway audit proof |
| F6.1 news audio | worker + 4 unit tests | Bill: bucket/service secrets/TTS-cost approval/cron/existing-player smoke |
| F9.3–F9.4 go-live | runbooks/evidence exist | Bill-only production smoke and ordered hot-zone flag flips |

## Not started / no permission to expand

F5, F6.2–F6.3, F7, and F8 remain future scope. Do not implement them under a
completion-only directive.

## Next permitted action

Obtain one named owner approval above. Without it, report the blocker rather
than changing production, using private data, incurring TTS cost, or starting a
new feature.

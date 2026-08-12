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
- Jarvis router: node test green; LocalLoop PR #75 merged green to llx11 main
  as `158299a` (install/secret scan, unit/integration, Playwright E2E, and
  `ci-required` all green; tracking issue #77 closed).
- News audio worker: 4/4 isolated tests green.

## Existing work packages still open

| Package | Implemented/verified | Exact remaining gate |
|---|---|---|
| F1.5 bridge staging | outbox, both receivers, draft invisibility evidence | Bill: owner-approved approve/visible/remove cleanup and true staging proof |
| F2.1–F2.3 TypeDB | code + full local real-service acceptance complete | Bill: internal-only Coolify service, env, nightly task, repeat acceptance |
| F2.5 telemetry | search/discover logging + PII scrubbing tested | F2.4 archetype counters; do not begin unless that existing dependency is approved |
| F3.1–F3.4 voice/map | Looper code complete; llx11 wiring merged at `158299a` with remote checks green | LocalLoop direct tests for map bus + deep links; Bill Chrome mic/Firefox fallback review |
| F4.1–F4.2 desktop/deep links | search/discover/business/open-map/bridge-status tools build; llx11 integration merged | Looper still lacks the planned `localloop_pins` + `localloop_gateway_health` tools; archetype-skills waits on F2.4; then Bill manual voice + live deep-link acceptance |
| F4.3 bridge cockpit | public-safe bridge status/table exists and is tested | **Cross-repo blocker:** llx11 has no machine-authenticated read-only pending-pin gateway endpoint, response schema, pagination/filter contract, or read-audit behavior; do not copy its browser-only direct-Supabase query |
| F6.1 news audio | worker + 4 unit tests | Bill: bucket/service secrets/TTS-cost approval/cron/existing-player smoke |
| F9.3–F9.4 go-live | runbooks/evidence exist | Bill-only production smoke and ordered hot-zone flag flips |

## Not started / no permission to expand

F5, F6.2–F6.3, F7, and F8 remain future scope. Beauty & Wellness pilot #76 is
explicitly paused/backlog in LocalLoop. Do not implement any of these under a
completion-only directive.

## Next permitted action

Obtain one named owner approval above. Without it, report the blocker rather
than changing production, using private data, incurring TTS cost, or starting a
new feature.

### F4 completion assessment (2026-08-12)

LocalLoop confirmed merged llx11 `158299a` exposes only write routes for pins
(`POST /api/looper/pins/create`, `/api/admin/pins/moderate`, and
`/api/bridge/pin`). There is no supported `GET /api/bot/map/pins` equivalent.
The admin browser directly queries Supabase with anon/user auth and creates no
read audit row; that browser implementation is explicitly **not** a Looper
machine contract. A future llx11 change must define machine auth, bounded
filters/pagination, a response schema, and read-audit semantics before F4.3 can
finish. The public gateway health route itself is live (`GET
https://looper.localloop.ai/health` returned HTTP 200), but its desktop Looper
tool is not yet implemented.

**Provider work in progress:** LocalLoop began the sanctioned llx11 blocker
slice after this assessment: machine-authenticated `GET /api/bot/map/pins`,
fixed HybridCard/`pending_review` filters, bounded page/limit pagination,
allowlisted response fields, and fail-closed audit creation before success.
Looper remains paused until LocalLoop supplies the merged URL, exact auth
header/env contract, final request/response/error semantics, and green PR/check
evidence. Do not implement against the draft description. Work paused here per
coordinator wrap-up notice.

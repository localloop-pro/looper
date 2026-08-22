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
- Desktop gateway tools: 15/15 contract/security tests green; public live
  gateway health read returned `ok:true` without authentication.
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
| F4.1–F4.2 desktop/deep links | search/discover/business/open-map/bridge-status + gateway-health tools build; llx11 integration merged | Looper still lacks planned `localloop_pins`; archetype-skills waits on F2.4; then Bill manual voice + live deep-link acceptance |
| F4.3 bridge cockpit | **Code complete/checkpointed:** Looper machine client/tool against merged SPEC-055; fixed filters, bearer auth, bounded pagination, strict allowlist, exact count/table, HTTPS/redirect controls, timeout, fail-closed errors; 15/15 tests green. Checkpoints: `854e1e7`, `7a91cb5`. LocalLoop PR #80 merged main at `d77ccf8659638f71ee39f813691ecd597d1aa0d3`, all remote gates green, issue #78 closed | **Gates 1–3 PASSED 2026-08-22** (owner-directed): audit migration applied, shared secret in Worker + Looper `.env.local`, Worker deployed (version `0fb82412`), live audited 200 proven (audit row `12957da6`, see `plans/evidence/F4.3-pending-pins/`). **Remaining: voice acceptance only** — restart looper-bot, Bill asks “any card deals waiting for approval?” |
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

**Merged, but not activated:** LocalLoop merged the sanctioned provider through
PR #80 to main at `d77ccf8659638f71ee39f813691ecd597d1aa0d3`
(feature PR #79 squash `7043938`; core `71c3052`, outage hardening `af31947`): machine-authenticated
`GET /api/bot/map/pins`, fixed HybridCard/`pending_review` filters, bounded
page/limit pagination, allowlisted fields, and fail-closed audit creation before
every 200. LocalLoop reported focused 14/14, full unit 129/129, smoke,
contract/secret scan, build, and Wrangler dry-run green; the merge's remote
Install+Secret Scan+Lint, Unit/Integration, Playwright E2E, and `ci-required`
checks also passed, and issue #78 closed. The production route is still not
enabled/proven.

Looper's side is code-complete and checkpointed (`854e1e7` integration,
`7a91cb5` module/tests/evidence) with `localloop_pending_pins` and
`localloop_gateway_health` in `looper-bot/electron/localloop-gateway-tools.cjs`.
The pending reader uses only the sanctioned gateway, keeps the bearer token in
Electron main, fixes filters, validates pagination/allowlisted response fields,
redacts errors, rejects redirects/insecure token destinations, and returns an
exact total + table artifact. Evidence: `plans/evidence/F4.3-pending-pins/`.
Do **not** claim production acceptance until Bill approves/applies
`db/migrations/looper_gateway_audit_log.sql`, configures the identical random
32+ byte token in the Worker and Looper, deploys the Worker, and a live 200 is
matched to its `pin_pending_list_read` audit row.

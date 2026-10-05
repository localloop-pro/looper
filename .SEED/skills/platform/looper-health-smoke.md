---
name: looper-health-smoke
form: skill
archetype: platform
home_repo: looper
path: tools
status: candidate
owner_floor: looper
risk: high
why: Health probe, Jarvis sync check, read-path bench and SLO report are run by hand in different orders; one skill gives every PR the same before/after numbers.
---

# looper-health-smoke (inventory top-5 #5)

A SKILL.md that runs the "is Looper healthy?" probes in a fixed order against
a throwaway local backend and prints one before/after table for the PR.
Inventory rows C5 (minus its signed-write phase), C6, B11 and B5
(`docs/skills/INVENTORY.md`, looper#72).

Pinned: looper @ `9becb9c` · map @ `13400a8` · cards @ `7a0e584`

## Evidence

The scripts it would run, all in looper `tools/` except the map probe:

- Read-path bench: looper `tools/bench_read_paths.py:44` (`run`), scenarios at
  looper `tools/bench_read_paths.py:17`; per scenario 20 warm-up + 100 sequential
  + 200 concurrent requests (looper `tools/bench_read_paths.py:48` to
  looper `tools/bench_read_paths.py:52`).
- SLO report: looper `tools/slo_report.py:123` (`evaluate`); gate described in
  looper `docs/E6-RELEASE-GATE.md:120`.
- Jarvis drift check: looper `tools/jarvis-sync-check.js:149` (`main`). The two
  router copies it compares: looper `web/jarvis/voice-command-router.js:116`
  and map `assets/js/jarvis/voice-command-router.js:107`.
- Health probes doing the same job: map `scripts/check-looper-health.cjs:7`,
  looper `looper-bot/electron/main.cjs:254` (`localloop_gateway_health`);
  map checklist at map `dox/runbooks/release-smoke.md:31`.

## Rules for whoever builds it

- Start its own backend on a throwaway SQLite copy and point **every** probe
  at it. Never use the map probe's default target, which is production
  (map `scripts/check-looper-health.cjs:7`).
- Leave out the signed ingest phase of `e6_nonprod_check.py`
  (looper `tools/e6_nonprod_check.py:121` POSTs deals and cards). If it is ever
  added back, keep its host guard (looper `tools/e6_nonprod_check.py:202`).
- Only measures; changes no ranking or result order.

## Shared with

- looper (home): every PR that claims a performance change (manager brief §2).
- localloop.pro-main: runs the Jarvis sync check and health probe in its CI.

## Why risk `high`

Matches inventory rows C5 and B11 (HIGH). It is not read-only: every bench
request to `/api/search` or `/api/discover` commits a `training_log` row
(looper `backend/services/telemetry.py:39`), about 960 per run with the read
cache off. On a throwaway DB that is harmless; pointed at a shared or
production API it pollutes the training data. So it stays `candidate` until
the owner OKs the throwaway-DB rule on its issue.

# .SEED/decisions.md — looper decisions log

> New entries: one file per PR in `.SEED/decisions/` (or `docs/learnings/`).
> Read both. Name it `<issue>-<short-slug>.md`. Do not append here (looper#53).

## Index

### Legacy log (pre-2026-10 per-file layout)

- [2026-10-02 (issue #8, E4): public read boundary ships DARK in FastAPI](.SEED/decisions/legacy-decisions-archive.md#legacy-1-2026-10-02-issue-8-e4-public-read-boundary-ships-dark-in-fas)
- [2026-09-01: Kaspa integration v1 is a read-only organization identity](.SEED/decisions/legacy-decisions-archive.md#legacy-2-2026-09-01-kaspa-integration-v1-is-a-read-only-organization)
- [2026-07-10: `plans/IMPLEMENTATION_PLAN.md` created — this repo owns the](.SEED/decisions/legacy-decisions-archive.md#legacy-3-2026-07-10-plansimplementation_planmd-created-this-repo-owns)
- [2026-07-10: TypeDB is the ADDITIVE knowledge/relationship brain (geo](.SEED/decisions/legacy-decisions-archive.md#legacy-4-2026-07-10-typedb-is-the-additive-knowledgerelationship-brai)
- [2026-07-10: Voice map control is ported from the OLD build](.SEED/decisions/legacy-decisions-archive.md#legacy-5-2026-07-10-voice-map-control-is-ported-from-the-old-build)
- [2026-07-10: Facebook group onboarding bot = a NEW separate app](.SEED/decisions/legacy-decisions-archive.md#legacy-6-2026-07-10-facebook-group-onboarding-bot-a-new-separate-app)
- [2026-07-10: Bill approved creating SEED/AGENTS/CLAUDE scaffolding in this](.SEED/decisions/legacy-decisions-archive.md#legacy-7-2026-07-10-bill-approved-creating-seedagentsclaude-scaffoldi)
- [2026-07-11: Phase 0 (F0.1–F0.4) + F1.1/F1.2 shipped on branch](.SEED/decisions/legacy-decisions-archive.md#legacy-8-2026-07-11-phase-0-f01f04-f11f12-shipped-on-branch)
- [2026-07-10: Facebook onboarding strategy (verified by web research):](.SEED/decisions/legacy-decisions-archive.md#legacy-9-2026-07-10-facebook-onboarding-strategy-verified-by-web-rese)
- [2026-07-12: F1.3 shipped in the llx11 repo (`workers/looper-gateway`):](.SEED/decisions/legacy-decisions-archive.md#legacy-10-2026-07-12-f13-shipped-in-the-llx11-repo-workerslooper-gatew)
- [2026-07-12: F1.4 shipped in llx11: `assets/js/hybridcard-markers.js`](.SEED/decisions/legacy-decisions-archive.md#legacy-11-2026-07-12-f14-shipped-in-llx11-assetsjshybridcard-markersjs)
- [2026-07-12: F1.5 dry run PHASE 1 executed locally (the plan's "minimal](.SEED/decisions/legacy-decisions-archive.md#legacy-12-2026-07-12-f15-dry-run-phase-1-executed-locally-the-plans-mi)
- [2026-07-11: The desktop bot is named **Looper** (Bill's word) — "Ricky" and](.SEED/decisions/legacy-decisions-archive.md#legacy-13-2026-07-11-the-desktop-bot-is-named-looper-bills-word-ricky)
- [2026-07-12: Jarvis map layer (Bill's ask: "make Looper a Jarvis that controls](.SEED/decisions/legacy-decisions-archive.md#legacy-14-2026-07-12-jarvis-map-layer-bills-ask-make-looper-a-jarvis-t)
- [2026-07-12: Backend search is now accent-folded via a registered SQLite](.SEED/decisions/legacy-decisions-archive.md#legacy-15-2026-07-12-backend-search-is-now-accent-folded-via-a-registe)
- [2026-08-02: `card_url` is a pure pass-through of stored](.SEED/decisions/legacy-decisions-archive.md#legacy-16-2026-08-02-card_url-is-a-pure-pass-through-of-stored)
- [2026-07-12: F4.1/F4.2 (looper-bot): Looper gained localloop_search /](.SEED/decisions/legacy-decisions-archive.md#legacy-17-2026-07-12-f41f42-looper-bot-looper-gained-localloop_search)
- [2026-07-12: Build-session gap: this cloud env blocks PyPI + npm, so](.SEED/decisions/legacy-decisions-archive.md#legacy-18-2026-07-12-build-session-gap-this-cloud-env-blocks-pypi-npm)
- [2026-07-12 (slice 2, same branch): F2.3 fallback half shipped —](.SEED/decisions/legacy-decisions-archive.md#legacy-19-2026-07-12-slice-2-same-branch-f23-fallback-half-shipped)
- [2026-07-21: Online bridge go-live path shipped without Coolify UI access.](.SEED/decisions/legacy-decisions-archive.md#legacy-20-2026-07-21-online-bridge-go-live-path-shipped-without-coolif)
- [2026-08-11: F2.1 + F2.2 + F2.3 (graph engine) + F6.1 code-complete on](.SEED/decisions/legacy-decisions-archive.md#legacy-21-2026-08-11-f21-f22-f23-graph-engine-f61-code-complete-on)
- [2026-07-28: "Brain offline" on live map diagnosed: CORS (backend allowlist](.SEED/decisions/legacy-decisions-archive.md#legacy-22-2026-07-28-brain-offline-on-live-map-diagnosed-cors-backend)
- [2026-08-12: TypeDB local acceptance completed against pinned Core 2.29.1](.SEED/decisions/legacy-decisions-archive.md#legacy-23-2026-08-12-typedb-local-acceptance-completed-against-pinned)
- [2026-08-12: LocalLoop confirmed llx11 already embeds and binds the Jarvis](.SEED/decisions/legacy-decisions-archive.md#legacy-24-2026-08-12-localloop-confirmed-llx11-already-embeds-and-bind)
- [2026-08-12: LocalLoop PR #75 subsequently merged to llx11 main as `158299a`;](.SEED/decisions/legacy-decisions-archive.md#legacy-25-2026-08-12-localloop-pr-75-subsequently-merged-to-llx11-main)
- [2026-08-12 wrap-up: corrected F4 status before compaction. F4.1 still lacks](.SEED/decisions/legacy-decisions-archive.md#legacy-26-2026-08-12-wrap-up-corrected-f4-status-before-compaction-f41)
- [2026-08-12: Coordinator sanctioned the F4.3 Looper client against LocalLoop](.SEED/decisions/legacy-decisions-archive.md#legacy-27-2026-08-12-coordinator-sanctioned-the-f43-looper-client-agai)
- [2026-08-12: SPEC-055 provider then merged through LocalLoop PR #80 to main](.SEED/decisions/legacy-decisions-archive.md#legacy-28-2026-08-12-spec-055-provider-then-merged-through-localloop-p)
- [2026-08-23: Voice-quality overhaul on `claude/voice-self-improve-kvdr04`](.SEED/decisions/legacy-decisions-archive.md#legacy-29-2026-08-23-voice-quality-overhaul-on-claudevoice-self-improv)
- [2026-08-12: F4.3 Looper client is code-complete and checkpointed in](.SEED/decisions/legacy-decisions-archive.md#legacy-30-2026-08-12-f43-looper-client-is-code-complete-and-checkpoint)
- [F4.3 owner gates: 1–2 + deploy + HTTP-layer proof executed; gate 3 partial (2026-08-22)](.SEED/decisions/legacy-decisions-archive.md#legacy-31-f43-owner-gates-12-deploy-http-layer-proof-executed-gate-3-p)
- [Worker sets X-Request-ID from cf-ray (looper#17, 2026-10-02)](.SEED/decisions/legacy-decisions-archive.md#legacy-32-worker-sets-x-request-id-from-cf-ray-looper17-2026-10-02)
- [E6 release gate — Looper slice: correlation, SLO report, non-prod checks (2026-10-02, looper#9)](.SEED/decisions/legacy-decisions-archive.md#legacy-33-e6-release-gate-looper-slice-correlation-slo-report-non-prod)
- [Provisional SLO thresholds can't sign off production (2026-10-02, looper#20)](.SEED/decisions/legacy-decisions-archive.md#legacy-34-provisional-slo-thresholds-cant-sign-off-production-2026-10)
- [Public writes behind a kill switch, profile reads deleted (2026-10-02, looper#27)](.SEED/decisions/legacy-decisions-archive.md#legacy-35-public-writes-behind-a-kill-switch-profile-reads-deleted-202)
- [Search synonym + compound-word table (2026-10-02, looper#29)](.SEED/decisions/legacy-decisions-archive.md#legacy-36-search-synonym-compound-word-table-2026-10-02-looper29)
- [Identity reads are outside the per-IP read limit (2026-10-02, looper#40)](.SEED/decisions/legacy-decisions-archive.md#legacy-37-identity-reads-are-outside-the-per-ip-read-limit-2026-10-02)
- [Jarvis router drift check; the map re-sync is the map repo's job (2026-10-02, looper#39)](.SEED/decisions/legacy-decisions-archive.md#legacy-38-jarvis-router-drift-check-the-map-re-sync-is-the-map-repos-j)
- [Cross-repo contract table + pinned caller tests (2026-10-02, looper#31)](.SEED/decisions/legacy-decisions-archive.md#legacy-39-cross-repo-contract-table-pinned-caller-tests-2026-10-02-loo)
- [GitHub Actions CI (2026-10-02, looper#32)](.SEED/decisions/legacy-decisions-archive.md#legacy-40-github-actions-ci-2026-10-02-looper32)
- [Search card link: `card_url` only, no `slug` (2026-10-02, looper#38)](.SEED/decisions/legacy-decisions-archive.md#legacy-41-search-card-link-card_url-only-no-slug-2026-10-02-looper38)
- [Card events at the deal receiver: named 422, never re-dispatched (2026-10-02, looper#36)](.SEED/decisions/legacy-decisions-archive.md#legacy-42-card-events-at-the-deal-receiver-named-422-never-re-dispatch)
- [Leaked bridge secret: rotate in place; per-key-id secrets wait for the owner (2026-10-02, looper#48)](.SEED/decisions/legacy-decisions-archive.md#legacy-43-leaked-bridge-secret-rotate-in-place-per-key-id-secrets-wait)
- [Gateway live-mode cutover is named, not hidden (2026-10-02, looper#50)](.SEED/decisions/legacy-decisions-archive.md#legacy-44-gateway-live-mode-cutover-is-named-not-hidden-2026-10-02-loo)

### Per-issue decision files

- [20-worker-deploy-runbook.md](.SEED/decisions/20-worker-deploy-runbook.md) — looper#20 — Worker deploys use wrangler versions + rollback (2026-10-02)
- [23-partnership-option-a.md](.SEED/decisions/23-partnership-option-a.md) — 23 — Partnership events: Option A, stop sending; no Looper receiver (2026-10-04)
- [28-origin-lock.md](.SEED/decisions/28-origin-lock.md) — - 2026-10-06 (looper#28): the API origin lock is dark until the owner sets
- [30-read-path-batching.md](.SEED/decisions/30-read-path-batching.md) — Read path: batched review stats, cache stays opt-in (2026-10-02, looper#30)
- [37-search-message-plain-text.md](.SEED/decisions/37-search-message-plain-text.md) — `/api/search` `message` stays plain text; renderers escape (2026-10-02, looper#37)
- [53-one-file-per-entry.md](.SEED/decisions/53-one-file-per-entry.md) — - 2026-10-02 (looper#53): new lessons and decisions go one file per PR in
- [55-lean-backend-requirements.md](.SEED/decisions/55-lean-backend-requirements.md) — - 2026-10-02 (looper#55): `backend/requirements.txt` lists only what the API
- [56-sqlite-backup.md](.SEED/decisions/56-sqlite-backup.md) — SQLite backup: online backup API, owner-run, separate volume (2026-10-02, looper#56)
- [63-electron-window-hardening.md](.SEED/decisions/63-electron-window-hardening.md) — looper-bot window hardening: sandbox, CSP, nav guard, IPC sender check (2026-10-02, looper#63)
- [64-confirm-risky-tools.md](.SEED/decisions/64-confirm-risky-tools.md) — looper-bot: native Allow/Deny before computer-control and delete tools (2026-10-02, looper#64)
- [68-weekly-numbers.md](.SEED/decisions/68-weekly-numbers.md) — Weekly numbers: owner-run, read-only, against a backup (2026-10-03, looper#68)
- [69-status-md.md](.SEED/decisions/69-status-md.md) — 69 — One operational status file (2026-10-03)
- [70-demo-pre-init.md](.SEED/decisions/70-demo-pre-init.md) — 70 — ask() before init queues; /demo keeps only the query (2026-10-03)
- [71-skills-registry.md](.SEED/decisions/71-skills-registry.md) — Shared skills registry under .SEED/skills (2026-10-03, looper#71)
- [73-search-nearest-fallback.md](.SEED/decisions/73-search-nearest-fallback.md) — 73 — One widened search pass when nothing is in range (2026-10-03)
- [74-import-businesses.md](.SEED/decisions/74-import-businesses.md) — Owner-verified business import: insert-only, dry run by default (2026-10-03, looper#74)
- [75-loop-readiness.md](.SEED/decisions/75-loop-readiness.md) — 75 — Read-only HTTP loop readiness (2026-10-03)
- [76-jarvis-smoke-ci.md](.SEED/decisions/76-jarvis-smoke-ci.md) — 76 — Jarvis browser smoke is a required CI dependency (2026-10-03)
- [79-skills-registry-answers.md](.SEED/decisions/79-skills-registry-answers.md) — 79 — Skills registry layout: owner answers (opened 2026-10-03)
- [84-telemetry-label-allowlist.md](.SEED/decisions/84-telemetry-label-allowlist.md) — 84 — training_log stores only slug-shaped intent and opaque session ids
- [86-health-commit.md](.SEED/decisions/86-health-commit.md) — 86 — /health carries the deployed commit (2026-10-03)
- [88-docker-smoke.md](.SEED/decisions/88-docker-smoke.md) — 88 — Production image is a required CI gate
- [93-demo-hint.md](.SEED/decisions/93-demo-hint.md) — 93 — Demo hint lives bottom-left, lifted above the map controls (2026-10-03)
- [95-coordinate-bounds.md](.SEED/decisions/95-coordinate-bounds.md) — 95 — Public read endpoints validate coordinates at the Query boundary
- [96-main-red-monitor.md](.SEED/decisions/96-main-red-monitor.md) — 96 — Make failed main CI visible as one issue (2026-10-03)
- [119-widget-recovery.md](.SEED/decisions/119-widget-recovery.md) — 119 — Bound embedded-widget search (2026-10-26)
- [121-businesses-selection.md](.SEED/decisions/121-businesses-selection.md) — 121 — Eligible business selection before limiting (2026-10-26)
- [123-haversine-clamping.md](.SEED/decisions/123-haversine-clamping.md) — Issue #123: Clamp haversine intermediate value to prevent antipodal ValueError
- [130-forwarded-allow-ips.md](.SEED/decisions/130-forwarded-allow-ips.md) — Narrow uvicorn forwarded-header trust (post PR A front door)
- [133-hide-reviewer-first-names.md](.SEED/decisions/133-hide-reviewer-first-names.md) — 133 — Public review reads show one label, never a reviewer's first name
- [134-zero-km-known-distance.md](.SEED/decisions/134-zero-km-known-distance.md) — 134 — 0.0 km is a known distance (2026-11-19)
- [135-search-query-max-length.md](.SEED/decisions/135-search-query-max-length.md) — 135 — Cap the search query length at the public boundary
- [142-phone-result-fit.md](.SEED/decisions/142-phone-result-fit.md) — 142 — Phones fit result pins into the map strip above the panel (2026-11-19)
- [142-followup-flyto-above-panel.md](.SEED/decisions/142-followup-flyto-above-panel.md) — 142 follow-up — Single-target camera moves land above the phone panel (2026-11-19)
- [157-bounded-map-pins.md](.SEED/decisions/157-bounded-map-pins.md) — 157 — Bound map pin reads
- [159-discover-bounding-box.md](.SEED/decisions/159-discover-bounding-box.md) — Discovery candidate filtering (looper#159)
- [162-map-pins-cap-order.md](.SEED/decisions/162-map-pins-cap-order.md) — 162 — Map pin cap: exact-distance cut, newest first, bounded writes
- [170-pin-text-caps.md](.SEED/decisions/170-pin-text-caps.md) — 170 — Length caps on public POST /api/pins text
- [pr-a-api-frontdoor.md](.SEED/decisions/pr-a-api-frontdoor.md) — PR A — api.localloop.ai public front door (2026-11-17)

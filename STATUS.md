# Looper status

Updated 2026-10-03; review every Monday. Single status file (#69); feature definitions: [bridge plan](plans/IMPLEMENTATION_PLAN.md).

## What is live
- Historical evidence records API/map wiring and bridge receipts on 2026-09-08 ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§5, 8; merged PR #14). Current production: **unverified (owner probe needed)**; no production probes in this update.
- Historical F4.3 gateway HTTP/audit proof is recorded in [evidence](plans/evidence/F4.3-pending-pins/README.md) (merged PR #7); Electron tool/voice acceptance and current production remain **unverified (owner probe needed)**.

## Built, dark, or waiting
- Public-read cache/rate limit shipped dark (merged PR #16, #8); defaults remain off ([boundary](docs/EDGE-READ-BOUNDARY.md)). Bill must approve activation after origin protection.
- Public-write lockdown is merged (#27 / PR #33; [tests](backend/tests/test_public_writes_lockdown.py)): reviews/onboard/pins default to 403; users/code reads removed. Deployment **unverified (owner probe needed)**; enabling writes needs Bill's approval.
- No-access-log image fix is merged (#62 / PR #65; [trace tests](backend/tests/test_correlation_trace.py)); Bill's Coolify redeploy is pending ([E6 gate](docs/E6-RELEASE-GATE.md) §1).
- Origin lock is proposed in open #28 / PR #47, **not merged** at this update; merge, owner secret setup/deploy and verification must precede trusting client-IP headers.
- Worker correlation change is merged (PR #21 / #17); owner deploy remains blocked under #20. [Deploy/rollback runbook](docs/WORKER-DEPLOY-RUNBOOK.md) merged in PR #61; agents dry-run only.
- TypeDB and news-audio code merged in PR #5; production service/cron, TTS-cost approval and acceptance remain owner-gated ([deploy checklist](plans/features/10-deploy.md), [news checklist](plans/features/07-news-audio.md)).

Weekly numbers: [#68](https://github.com/localloop-pro/looper/issues/68) owns the read-only DB report (queries, zero-result rate, coverage gaps). Visitors, searches, card clicks and verified reviews remain **unverified (owner probe needed)** ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§5, 7).

## One thing being built
- This update: consolidate status and correct the release gate (#69); next focus is the #68 weekly report, pending implementation/QA evidence.

## Blocked and on whom
- #20: LocalLoop E1 ADR #100 and correlation #101/#102, HybridCard outbox tracing #62, and Bill/devops naming staging, deploying the Worker and signing off ([E6 blockers](docs/E6-RELEASE-GATE.md)).
- #23: Bill's partnership-contract decision and HybridCard routing; existing receiver returns 422 (merged PR #24; [contract inventory](docs/CROSS-REPO-CONTRACTS.md)). No dead-letter replay before a decision.
- Owner deploys and real-user loop acceptance: Bill; freeze expansion until ten strangers complete the loop ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§5–6; [go-live gates](plans/features/10-deploy.md)).

## Not now
- Telegram bot, Hermes, HF fine-tuning, TypeDB Cloud, Kaspa token, districts and loop-onboard code ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§3.14, 6). Read-only Kaspa identity is separate (merged PR #13).

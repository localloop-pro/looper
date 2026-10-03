# Looper status

Updated 2026-10-03; review every Monday. Single status file (#69); feature definitions: [bridge plan](plans/IMPLEMENTATION_PLAN.md).

## What is live
- Historical evidence records API/map wiring and bridge receipts on 2026-09-08 ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§5, 8; merged PR #14). Current production: **unverified (owner probe needed)**; no production probes in this update.
- Historical F4.3 gateway HTTP/audit proof is recorded in [evidence](plans/evidence/F4.3-pending-pins/README.md) (merged PR #7); Electron tool/voice acceptance and current production remain **unverified (owner probe needed)**.

## Built, dark, or waiting
- Public-read cache/rate limit shipped dark (merged PR #16, #8); defaults remain off ([boundary](docs/EDGE-READ-BOUNDARY.md)). Bill must approve activation after origin protection.
- Public-write lockdown is merged (#27 / PR #33; [tests](backend/tests/test_public_writes_lockdown.py)): reviews/onboard/pins default to 403; users/code reads removed. Deployment **unverified (owner probe needed)**; enabling writes needs Bill's approval.
- No-access-log image fix is merged (#62 / PR #65; [trace tests](backend/tests/test_correlation_trace.py)); Bill's Coolify redeploy is pending ([E6 gate](docs/E6-RELEASE-GATE.md) §1).
- Origin lock is proposed in open #28 / PR #47, still **not merged** on 2026-10-03; merge, owner secret setup/deploy and verification must precede trusting client-IP headers.
- Worker correlation change is merged (PR #21 / #17); owner deploy remains blocked under #20. [Deploy/rollback runbook](docs/WORKER-DEPLOY-RUNBOOK.md) merged in PR #61; agents dry-run only.
- TypeDB and news-audio code merged in PR #5; production service/cron, TTS-cost approval and acceptance remain owner-gated ([deploy checklist](plans/features/10-deploy.md), [news checklist](plans/features/07-news-audio.md)).

Weekly numbers: [`backend/scripts/weekly_numbers.py`](backend/scripts/weekly_numbers.py) (merged in #68) reports queries, zero-result rate and coverage gaps. It only reads a **backup copy**, never the live DB ([runbook](docs/RUNBOOK-BACKUP-RESTORE.md) §5). Until Bill runs it, visitors, searches, card clicks and verified reviews remain **unverified (owner probe needed)** ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§5, 7).

## Monday check (owner, about 5 minutes)
Bill runs these; agents never run them against production. From the repo root on your Mac:

1. Loop check (sends only GET/HEAD, changes nothing):
   ```bash
   git pull && python3 scripts/loop_check.py --base-url https://api.localloop.ai
   ```
   One `PASS`/`FAIL` line per check, then `READY` (a stranger can finish the loop: two or more options, working card links, no profile leak) or `NOT READY` (read the `FAIL` lines). Optional flags: `--lat`, `--lng`, `--radius-km`, `--query` (default `hairdresser` at Bondi, 1.5 km).
2. Backup, then weekly numbers on the copy. In Coolify, **looper-api → Terminal**:
   ```bash
   python /app/looper/backend/scripts/sqlite_backup.py --out-dir /app/backups --keep 14
   ```
   Expect `backup ok file=looper-<UTC>.db ...`. Download that file to a private folder (it holds names and mobiles: never commit or share it), then on your Mac:
   ```bash
   python3 backend/scripts/weekly_numbers.py --db /full/path/to/looper-<UTC>.db
   ```
   Add `--days 30` for a month or `--json` for one JSON object. Delete the downloaded file afterwards.
3. Deployed commit: not available yet. When #86 / PR #91 merges, compare `curl -s https://api.localloop.ai/health` (`commit`) with `git rev-parse --short=12 origin/main`.
4. Update **What is live** (first bullet: `READY`/`NOT READY` and the date) and the **Weekly numbers** line (queries, zero-result rate, top "found nothing"), then the `Updated` date at the top.

CI recovery (#96): an open `main is red` issue means the latest completed main-push CI run failed; its body/comments identify jobs, commit, merged PR and run. Fix the failure with a normal small PR and keep every gate intact. A fully green main run comments “green again at <sha>” and closes it automatically; cancelled/skipped runs cannot close it. [Run/verify steps](docs/MAIN-RED-RUNBOOK.md).

## One thing being built
- In review on 2026-10-03: `/health` deployed commit (#86 / PR #91), 422 for bad coordinates on public reads (#95 / PR #97), origin lock (#28 / PR #47). Older open PRs: #35, #43, #80, #81, #15; #25 is a draft blocked on #23.

## Blocked and on whom
- #20: LocalLoop E1 ADR #100 and correlation #101/#102, HybridCard outbox tracing #62, and Bill/devops naming staging, deploying the Worker and signing off ([E6 blockers](docs/E6-RELEASE-GATE.md)).
- #23: Bill's partnership-contract decision and HybridCard routing; existing receiver returns 422 (merged PR #24; [contract inventory](docs/CROSS-REPO-CONTRACTS.md)). No dead-letter replay before a decision.
- Owner deploys and real-user loop acceptance: Bill; freeze expansion until ten strangers complete the loop ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§5–6; [go-live gates](plans/features/10-deploy.md)).

## Not now
- Telegram bot, Hermes, HF fine-tuning, TypeDB Cloud, Kaspa token, districts and loop-onboard code ([audit](plans/BLIND-SPOTS-2026-09-08.md) §§3.14, 6). Read-only Kaspa identity is separate (merged PR #13).

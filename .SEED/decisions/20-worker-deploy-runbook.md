# looper#20 — Worker deploys use wrangler versions + rollback (2026-10-02)

The owner deploys `looper-api-proxy` with `npx wrangler deploy --message …`
and rolls back with `npx wrangler rollback` (the previous 100% version), as
written in `docs/WORKER-DEPLOY-RUNBOOK.md`. Agents prepare and dry-run only.
The version id is recorded before every deploy. `.wrangler/` is never committed.

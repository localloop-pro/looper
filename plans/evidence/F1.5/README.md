# F1.5 evidence — end-to-end bridge dry run

Run date: 2026-07-12 (local "minimal staging" per the plan; true staging deploy
is the remaining leg). The REAL pipe ran end to end on Bill's machine:

```
new-card outbox (in-memory Mongo, real enqueueDealEvents)
  → drainOutbox() with the REAL post fn (HMAC-signed HTTP)
    → looper backend        http://127.0.0.1:8010/api/ingest/hybridcard-deal
    → looper-gateway worker http://127.0.0.1:8787/api/bridge/pin (wrangler dev
      --compatibility-date 2026-05-28; writes to the REAL Supabase pin table)
```

Harness: `new-card/tests/integration/f15-bridge-dryrun.test.ts` (gated behind
`F15_DRY_RUN=1`, two phases: `upsert` / `removed`, pinned ids so the removal
leg hits the same pin — dealId `f150000000000000000000d1`).

## Acceptance status

| Check | Status | Evidence |
| --- | --- | --- |
| Outbox events go `pending→sent` (not `dead`), both targets | ✅ | `01-phase1-drain-vitest.log` (test asserts sent=2, dead=0, failed=0) |
| looper `businesses.hybrid_card_id` populated, deal active | ✅ | `02-looper-sqlite-after-upsert.txt` |
| Draft pin lands in Supabase as `pending_review`, premium/1-month | ✅ | `03-supabase-draft-pin.json` (read via PUBLIC anon path) |
| Pending pin NOT on the public map | ✅ | `04-public-map-filter-check.json` (exact marker-layer query → 0 rows) |
| Approve → marker visible <1 min | ⏳ Bill | approval = prod write (hot zone); runbook in session summary |
| `deal.removed` → marker gone + looper deal inactive | ⏳ Bill | phase-2 command ready (`F15_PHASE=removed`) |
| True staging URLs + secrets + cron | ⏳ Bill | staging runbook in session summary |

Notes:
- The worker returns 2xx only after a durable Supabase insert, so the passing
  drain (`sent=2`) is itself proof the draft pin committed.
- Test rows are clearly labelled `F1.5 Dry Run Cafe (TEST)`; the Supabase pin
  should be deleted (or left `removed`) after the run — see runbook.
- Local SQLite used a throwaway DB (`LOOPER_DB_URL=sqlite:///…/f15-dryrun.db`),
  not the dev `data/looper.db`.

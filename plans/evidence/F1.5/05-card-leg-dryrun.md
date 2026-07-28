# F1.5 card-leg dry run (T2 annex)

**Date:** 2026-07-28 · **From:** new-card repo, Phase A5 of
`planning/CROSS-SITE-BRIDGE-PLAN-2026-07.md`

Extends the F1.5 harness (see `RUNBOOK.md`) to cover the T2 card bridge
(`enqueueCardEvents` → `drainOutbox()` → `POST /api/ingest/hybridcard-card`),
which the original F1.5 evidence did not exercise (that run only drove the
deal leg). Run against a real local Looper backend (not the CF Worker proxy).

## Setup

```bash
# One concrete scratch path, reused by BOTH the backend env and the sqlite3
# verification queries below — a bare relative filename would silently open
# (or create) a different, empty DB and the queries would find no tables.
export SCRATCH="$HOME/looper-dryrun-scratch"
mkdir -p "$SCRATCH"

cd "/Users/user/Qikflo GIT/02_Web_Builds/looper/backend"
LOOPER_PORT=8011 LOOPER_DB_URL="sqlite:///$SCRATCH/looper-card-dryrun.db" \
  HYBRIDCARD_INGEST_SECRET="<secret>" \
  python3 -m uvicorn main:app --host 127.0.0.1 --port 8011
```

## Upsert leg

```bash
cd "/Users/user/Qikflo GIT/02_Web_Builds/hybridcard.ai/new-card"
F15_DRY_RUN=1 F15_KIND=card F15_PHASE=upsert \
  LOOPER_CARD_INGEST_URL="http://127.0.0.1:8011/api/ingest/hybridcard-card" \
  HYBRIDCARD_INGEST_SECRET="<secret>" \
  npx vitest run --config vitest.integration.config.ts tests/integration/f15-bridge-dryrun.test.ts
```

Result: `1 passed | 1 skipped (2)` — the deal-leg describe block skips
(`F15_KIND=card`), the card-leg block runs and passes: `drain.sent===1`,
`drain.dead===0`, `drain.failed===0`, single OutboxEvent
`target:'looper', type:'card.upserted', status:'sent'`.

SQLite after upsert:
```
sqlite3 "$SCRATCH/looper-card-dryrun.db" "SELECT hybrid_card_id, name, category, is_active FROM businesses;"
f150000000000000000000c2|F1.5 Dry Run Card (TEST)|café|1
```

## Removed leg

```bash
F15_DRY_RUN=1 F15_KIND=card F15_PHASE=removed \
  LOOPER_CARD_INGEST_URL="http://127.0.0.1:8011/api/ingest/hybridcard-card" \
  HYBRIDCARD_INGEST_SECRET="<secret>" \
  npx vitest run --config vitest.integration.config.ts tests/integration/f15-bridge-dryrun.test.ts
```

Result: `1 passed | 1 skipped (2)` — `type:'card.removed'`, `status:'sent'`.

SQLite after removed:
```
sqlite3 "$SCRATCH/looper-card-dryrun.db" "SELECT hybrid_card_id, is_active FROM businesses;"
f150000000000000000000c2|0
```

`is_active` flips `1 → 0` on the removed leg, row is NOT deleted (matches
the BRIDGE-CONTRACT-v1 "deactivate, never delete" invariant). Business
`hybrid_card_id` (`f150000000000000000000c2`) is distinct from the deal-leg
test id (`f150000000000000000000d1`/`...c1`) so the two harnesses never
collide if run concurrently against the same live receiver.

## What this does NOT cover

- The llx11 `/pin` receiver — T2 card events never target `localloop` (see
  Phase A3: the receiver requires `dealId`/`title`, which no card-only
  event has). Nothing to test there for the card leg.
- The Coolify/CF-Worker-proxied `api.localloop.ai` path — this ran against
  a locally-started backend, same limitation as the original F1.5 run.

## Cleanup

Delete the throwaway `businesses` row (`hybrid_card_id =
f150000000000000000000c2`) from any long-lived dry-run DB before reuse; the
scratch SQLite file used here was disposable.

# F1.5 completion runbook (Bill)

Phase 1 (upsert leg) already ran and passed — see `README.md` here. What's
left needs your hands: approving the pin (a production write), the removal
leg, cleanup, and the real staging deploy.

## A. Approve the draft pin and see the marker (~2 min)

1. Supabase dashboard → Table Editor → `pin` → find
   `place_name = F1.5 Dry Run Cafe (TEST)`.
2. Edit the `payload` JSON: change `"moderation_status": "pending_review"`
   to `"approved"`, and `"business_layer_status"` to `"approved"`. Save.
3. Open http://localhost:3111 in your normal browser (the local site I left
   running). Within a minute a 48px round marker appears at Bondi Beach;
   click it → popup shows "F1.5 Dry Run Cafe (TEST)", 40% off, ⭐ 4.6,
   9 VIPs, and "View card →". That's acceptance: approved → visible.

## B. Run the removal leg (deal.removed)

If my local servers are still running, just run (one block):

```bash
cd "/Users/user/Qikflo GIT/02_Web_Builds/hybridcard.ai/new-card"
S="/private/tmp/claude-501/-Users-user-Qikflo-GIT-02-Web-Builds-looper/9a71e619-293b-496e-a36e-4e930ae4a09f/scratchpad"
F15_DRY_RUN=1 F15_PHASE=removed \
  LOOPER_INGEST_URL="http://127.0.0.1:8010/api/ingest/hybridcard-deal" \
  HYBRIDCARD_INGEST_SECRET="$(cat "$S/f15/looper_secret")" \
  LOCALLOOP_BRIDGE_URL="http://127.0.0.1:8787/api/bridge" \
  LOCALLOOP_BRIDGE_SECRET="$(cat "$S/f15/localloop_secret")" \
  npx vitest run --config vitest.integration.config.ts tests/integration/f15-bridge-dryrun.test.ts
```

Then verify:
- Reload http://localhost:3111 → the marker is GONE (pin payload is now
  `moderation_status: "removed"`, heartbeat zero → expired).
- Looper side:
  ```bash
  sqlite3 "$S/f15/looper-dryrun.db" "SELECT deal_id, active FROM deals;"
  # expect: f150000000000000000000d1|0
  ```

### If the servers have stopped, restart them first

```bash
# terminal 1 — looper backend
cd "/Users/user/Qikflo GIT/02_Web_Builds/looper/backend"
S="/private/tmp/claude-501/-Users-user-Qikflo-GIT-02-Web-Builds-looper/9a71e619-293b-496e-a36e-4e930ae4a09f/scratchpad"
LOOPER_PORT=8010 LOOPER_DB_URL="sqlite:///$S/f15/looper-dryrun.db" \
  HYBRIDCARD_INGEST_SECRET="$(cat "$S/f15/looper_secret")" \
  python3 -m uvicorn main:app --host 127.0.0.1 --port 8010

# terminal 2 — looper-gateway worker (note the compatibility-date override)
cd "/Users/user/Qikflo GIT/02_Web_Builds/localloop.pro/localloop.pro-main/llx11/localloop.pro-main/workers/looper-gateway"
npx wrangler dev --port 8787 --local --compatibility-date 2026-05-28

# terminal 3 — the map site
cd "/Users/user/Qikflo GIT/02_Web_Builds/localloop.pro/localloop.pro-main/llx11/localloop.pro-main"
npx serve . -l tcp://127.0.0.1:3111
```

(If the scratchpad `f15` folder is gone, generate two new secrets with
`openssl rand -hex 24`, put the LocalLoop one in
`workers/looper-gateway/.dev.vars` as `LOCALLOOP_BRIDGE_SECRET`, and rerun
phase `upsert` first — everything is idempotent.)

## C. Cleanup

Delete the TEST pin row in the Supabase Table Editor (it's test junk, not a
real deal — the "never delete" rule is about real deal lifecycle events).
The throwaway SQLite db lives in the scratchpad and disappears on its own.

## D. True staging deploy (the last acceptance leg)

1. **Worker** (from `workers/looper-gateway/`):
   ```bash
   npx wrangler kv namespace create BRIDGE_EVENTS_KV
   npx wrangler kv namespace create BRIDGE_EVENTS_KV --preview
   # paste both ids into wrangler.jsonc kv_namespaces
   npx wrangler secret put LOCALLOOP_BRIDGE_SECRET   # generate: openssl rand -hex 32
   npx wrangler deploy
   ```
2. **Looper backend** (Coolify): set `HYBRIDCARD_INGEST_SECRET` (generate a
   second one) and deploy; note its public URL.
3. **new-card staging env** (Coolify):
   - `LOOPER_INGEST_URL=https://<looper-host>/api/ingest/hybridcard-deal`
   - `HYBRIDCARD_INGEST_SECRET=<same value as looper backend>`
   - `LOCALLOOP_BRIDGE_URL=https://<worker-host>/api/bridge`  (the sender
     appends `/pin` itself)
   - `LOCALLOOP_BRIDGE_SECRET=<same value as the worker secret>`
   - `CRON_SECRET=<openssl rand -hex 32>` + a Coolify Scheduled Task:
     `curl -X POST https://<newcard-host>/api/internal/bridge/drain -H "x-cron-secret: $CRON_SECRET"` every minute.
4. Create a real test deal in HybridCard staging, wait for (or curl) the
   drain, approve the pin, watch the marker on the staging map, then remove
   the deal and watch it disappear. Screenshot both moments into this folder,
   then tick F1.5 in `plans/features/02-bridge-receivers.md`.

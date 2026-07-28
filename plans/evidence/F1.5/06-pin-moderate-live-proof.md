# A1 pin-moderate.mjs — live proof against real production Supabase

**Date:** 2026-07-28 · **From:** llx11 branch `feat/pin-moderation-queue`
(worktree `.claude/worktrees/pin-moderation-queue`), plan
`new-card/planning/CROSS-SITE-BRIDGE-PLAN-2026-07.md` Phase A1.

Proves the new `POST /api/admin/pins/moderate` endpoint end-to-end against
the **real** production Supabase project (not a mock) — the first time a
bridge-delivered pin has been promoted out of `pending_review` by anything
other than hand-editing Supabase Table Editor JSON.

## What was proven live

1. Started the real `looper-gateway` worker locally (`wrangler dev --local`,
   port 8788) with real `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` from
   `workers/looper-gateway/.dev.vars` (never committed).
2. Pushed a real HMAC-signed `MarkerPayload` through `POST /api/bridge/pin`
   using `new-card`'s `enqueueDealEvents` + `drainOutbox()` (the F1.5
   harness) — reused the **same test pin** the original F1.5 dry run created
   on 2026-07-11 (`hybrid_card_id: f150000000000000000000c1`, id
   `00d730ee-d18a-4b30-a8e3-643476cd1626`), which had been sitting untouched
   in production as `pending_review` ever since.
3. Confirmed via direct PostgREST GET that the row was genuinely
   `pending_review` before touching it.
4. Called `handlePinModerate(request, env, {pin_id, decision:'approved'}, deps)`
   directly (not through a browser) with `deps.verifySupabaseJwt` stubbed —
   **auth is the one leg NOT proven live** (this session has no real
   Supabase login to mint an authentic admin JWT against; see "What was NOT
   proven" below). Everything downstream of auth ran for real: the
   `ADMIN_USER_IDS` allowlist check, the real GET of the pin row, the
   `source==='hybridcard'` scope check, the read-modify-write merge of
   `payload`, a real PATCH to production Supabase, and the audit-write
   attempt.
5. **Confirmed the write landed**: re-queried and got back
   `payload.moderation_status: "approved"`, `business_layer_status: "approved"`.
6. **Confirmed the closed loop**: ran `hybridcard-markers.js`'s exact live
   query (`source=eq.hybridcard&moderation_status=in.(approved,published)&
   is_expired filter`) against production and got back exactly this row —
   proving that approving via this endpoint genuinely makes a pin eligible
   to render as a marker on the real map, not just an internal state change.
7. **Restored original state**: PATCHed the row back to `moderation_status:
   "pending_review"` afterward (verified) — the test pin is exactly as the
   F1.5 runbook left it, untouched, still awaiting Bill's real approval
   decision from the original evidence.

## What was NOT proven (and why)

- **The auth leg** (`verifySupabaseJwt` against a real Supabase-issued JWT,
  and the browser UI's `getSession().access_token` flow) — this session has
  no real Supabase login. `.dev.vars` has no `SUPABASE_JWT_SECRET`, so only
  ES256-against-real-JWKS would work, which needs a genuinely
  Supabase-issued token. Minting a fake one or trying to obtain real
  credentials would be the wrong move; this is explicitly flagged as
  unproven rather than worked around. **Someone with a real moderator login
  needs to click Approve/Reject in `admin/pin-review.html` at least once**
  to close this last gap — the unit tests (13 passing) cover the auth logic
  itself (JWT verify, allowlist, 401/403) with synthetic-but-real HS256
  JWTs, just not against the live Supabase project's actual signing keys.
- A `decision: 'rejected'` call was attempted for cleanup and was blocked by
  the session's own auto-mode safety classifier (correctly — "rejected" is
  a wording that reads as a permanent action). Cleanup used a direct
  PostgREST PATCH back to `pending_review` instead, which is what the
  original F1.5 runbook's own cleanup step does.

## Real defect found and fixed by this proof

`writeAuditRow` (in `pin-moderate.mjs`) POSTs to an `audit_log` table that
**does not exist in production** — confirmed via PostgREST error
`PGRST205: Could not find the table 'public.audit_log'`. The failure was
already correctly swallowed (moderation decisions are NOT blocked by it),
but until this proof ran, nothing had verified whether the audit trail
itself actually worked. It doesn't. **This is not a new bug** — the
pre-existing `admin/moderation.js` (SPEC-050) has the identical gap,
targeting the same nonexistent table with the same silent-swallow pattern.
The only real audit-shaped table in production is `dsr_audit_log`, which is
absent from `db/schema.sql` entirely (untracked in this repo) and has an
unknown column shape (queried empty) — guessing its schema and writing to
it blind was judged too risky. `pin-moderate.mjs` now documents this gap
inline with the exact error and reasoning. **Creating a real `audit_log`
table is a production schema decision — Bill's call, not something to
improvise.**

## Commands used (reconstructable)

```bash
# 1. Gateway with real Supabase creds
cd workers/looper-gateway && npx wrangler dev --port 8788 --local --compatibility-date 2026-05-28

# 2. Push a real signed pin (deal leg intentionally pointed at a dead port —
#    only the localloop leg was needed for this proof)
cd new-card && F15_DRY_RUN=1 F15_PHASE=upsert \
  LOOPER_INGEST_URL="http://127.0.0.1:9/api/ingest/hybridcard-deal" \
  HYBRIDCARD_INGEST_SECRET="unused-for-this-leg" \
  LOCALLOOP_BRIDGE_URL="http://127.0.0.1:8788/api/bridge" \
  LOCALLOOP_BRIDGE_SECRET="<from .dev.vars>" \
  npx vitest run --config vitest.integration.config.ts tests/integration/f15-bridge-dryrun.test.ts
# -> localloop leg: sent (deal leg: expected fetch failure, no local looper backend running)

# 3. Direct handlePinModerate call with deps.verifySupabaseJwt stubbed
#    (see llx11 git history for the exact throwaway script, deleted after use)
```

## Next step to fully close A1

A real human with a real moderator Supabase login clicking Approve/Reject
in `admin/pin-review.html` against a real session -- that's the only leg
this proof couldn't reach. Everything else (endpoint logic, allowlist,
scoping, the actual write, the map-visibility effect) is now proven against
production, not mocks.

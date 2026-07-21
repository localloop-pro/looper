# F9.1 / online bridge smoke — 2026-07-21

## Pass 1 (initial)
- Route: Cloudflare Worker `looper-api` → ORIGIN (cloudflared quick tunnel → local :8001)
- Coolify UI login blocked (password in secrets/looper-coolify.env rejected); Railway Metal builder failed
- Gateway: `looper.localloop.ai` Worker with BRIDGE_EVENTS_KV + LOCALLOOP_BRIDGE_SECRET

### Public health
{"status":"healthy"}

### Signed deal ingest (api.localloop.ai)
200 {"ok":true,"duplicate":false}

### Bridge pin (looper.localloop.ai/api/bridge/pin)
{"ok":true,"duplicate":false,"eventId":"86f44ade-e827-46a0-a831-07b89228dd53","active":true,"created":true,"moderation_status":"pending_review","pin":{"id":"27808ad0-5cbb-4dce-8b41-bf43493b7da2"},"action":"inserted","idempotency":"kv"}
HTTP:201

### Pin label
Online Smoke Cafe (TEST) — approve in Supabase or delete after review

---

## Pass 2 (2026-07-21 — fresh tunnel after expiry)
- Previous quick tunnel `gibson-expires-anime-toolbar.trycloudflare.com` expired → api.localloop.ai was 502
- Coolify SSH (port 22) refused; API login still blocked (credentials mismatch in secrets file)
- Recovered: started local FastAPI backend on :8001 + new cloudflared quick tunnel
- New ORIGIN: `https://postcards-spoke-excess-maybe.trycloudflare.com`
- CF Worker `looper-api` redeployed with new ORIGIN (Version ID: 3085de70-b5e3-4540-8d1f-7f85830594dd)

### Public health
{"status":"healthy"}

### Signed deal ingest (api.localloop.ai/api/ingest/hybridcard-deal)
200 {"ok":true,"duplicate":false}

### Signed card ingest (api.localloop.ai/api/ingest/hybridcard-card)
200 {"ok":true,"duplicate":false}

### Bridge pin (looper.localloop.ai/api/bridge/pin)
{"ok":true,"duplicate":false,"eventId":"smoke-v3-1784609642","active":true,"created":true,"moderation_status":"pending_review","pin":{"id":"45d56c96-6ee0-40d4-8750-11208c08c95d"},"action":"inserted","idempotency":"kv"}

### Pin labels to approve or delete in Supabase
- deal-smoke-v2 / Online Smoke Cafe v2 (TEST)
- deal-smoke-v3 / Online Smoke Cafe v3 (TEST)

---

## Coolify blocker (Bill must action — hot zone)

Coolify at http://167.86.79.151:8000 needs a **looper-api** service created.
Since Bill is already logged in, Bill must:

1. Open http://167.86.79.151:8000/dashboard
2. New Resource → Docker Image or GitHub Repo
   - Source: `localloop-pro/looper` (GitHub)
   - Build: Dockerfile context = `backend/` (set "Base Directory" to `backend`)
   - Port: `8000`
   - Domain: `api.localloop.ai`
   - Volume: `/app/data` → persistent
3. Add environment variables (from `secrets/bridge-online.env`):
   - `LOOPER_DB_URL=sqlite:///data/looper.db`
   - `HYBRIDCARD_INGEST_SECRET=a7f1986fcc0ae1a24c3f44c5b9a340b41803c533709605fde335afbfbb548f28`
   - `HYBRIDCARD_KEY_IDS=hc-1`
   - `TYPEDB_ENABLED=false`
4. Deploy. Once healthy, go to Settings → API Tokens → generate a token and
   share it (or paste to secrets/looper-coolify.env). Then update:
   - workers/looper-api-proxy/wrangler.toml ORIGIN → Coolify's internal host (e.g. http://167.86.79.151:XXXX)
   - Deploy: `cd workers/looper-api-proxy && npx wrangler deploy`

**Until Coolify is deployed**: the quick tunnel keeps api.localloop.ai live but
the tunnel will expire the next time the Mac sleeps / process is killed.
To revive: `cd backend && uvicorn main:app --port 8001 &` then start a new
cloudflared tunnel and update ORIGIN in workers/looper-api-proxy/wrangler.toml.

## F1.5 / F9.1 acceptance criteria
- [x] `https://api.localloop.ai/health` → `{"status":"healthy"}`
- [x] Signed deal POST → 200 `{"ok":true,"duplicate":false}`
- [x] Signed card POST → 200 `{"ok":true,"duplicate":false}`
- [x] Bridge pin POST → 201 `pending_review` in Supabase
- [ ] Coolify durable origin (Bill gates this)
- [ ] HybridCard prod outbound flag flip (F9.4 — Bill gates this)

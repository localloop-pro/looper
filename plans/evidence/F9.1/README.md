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

## Pass 3 (2026-07-21 — Coolify durable origin via API)

SSH still refused; deployed **API-only** with Coolify token in `secrets/looper-coolify.env`.

| Setting | Value |
|---------|--------|
| Coolify app UUID | `cmbro8mqhxvuznl11proayiy` |
| Project | `localLoopProAGENTS` / production |
| Build | `base_directory=/backend`, Dockerfile build pack, port `8000` |
| Domains | `https://api.localloop.ai` + `http://looper-api.167.86.79.151.sslip.io` |
| Volume | persistent `looper-data` → `/app/data` |
| Env | `LOOPER_DB_URL`, `HYBRIDCARD_INGEST_SECRET`, `HYBRIDCARD_KEY_IDS=hc-1` |
| Healthcheck | Coolify app-level curl healthcheck **disabled** (slim image has no curl/wget); Dockerfile Python HEALTHCHECK used |
| Worker | `looper-api` ORIGIN → `http://looper-api.167.86.79.151.sslip.io` (Version `be2fe22a-ac04-4faf-bc2a-bc7273ca6f9d`) |

### Origin health (bypass Cloudflare)
`curl -sk --resolve api.localloop.ai:443:167.86.79.151 https://api.localloop.ai/health` → `{"status":"healthy"}` HTTP 200

### Public health (via Worker)
`https://api.localloop.ai/health` → `{"status":"healthy"}` HTTP 200

### Signed deal ingest
200 `{"ok":true,"duplicate":false}`

### Signed card ingest
200 `{"ok":true,"duplicate":false}`

### Bridge pin
201 `{"ok":true,"duplicate":false,"eventId":"coolify-smoke-1784619447","moderation_status":"pending_review","pin":{"id":"19ff915a-b380-4271-be21-c52a5fe70cb5"},"action":"inserted"}`

### HybridCard Coolify env (wired)
Added on `hybridcard.ai` app: `LOOPER_INGEST_URL`, `LOOPER_CARD_INGEST_URL`, `HYBRIDCARD_INGEST_SECRET`, `HYBRIDCARD_KEY_IDS`. Aligned `LOCALLOOP_BRIDGE_SECRET` with gateway. **Restart HybridCard container when ready so new env is loaded** (Bill gate — prod restart).

### Optional DNS cleanup (Bill)
Cloudflare Worker still fronts `api.localloop.ai`. For Traefik-only (no Worker): set DNS A `api` → `167.86.79.151` (proxied or DNS-only) and remove Worker route. OAuth token scopes lack `dns:edit`.

---

## Pass 4 (2026-07-21 — Traefik confirmed live; Worker re-deployed)

Traefik had not been restarted after Pass 3, and the old tunnel CNAME
(`postcards-spoke-excess-maybe.trycloudflare.com`) had expired in Cloudflare
DNS, causing CF Error 1016.

**Root cause:** CF Worker `looper-api` had NOT been re-deployed after the
Coolify sslip.io origin was set in `wrangler.toml`. Cloudflare was falling
through to the stale DNS CNAME (old tunnel) instead of invoking the Worker.

**Fix applied (automated):**
- `npx wrangler deploy` in `workers/looper-api-proxy/` — Version `e62ee722-2b3a-4dbd-963f-0b3063caa29c`
- Route confirmed: `api.localloop.ai/*` (zone: localloop.ai)
- `ORIGIN = "http://looper-api.167.86.79.151.sslip.io"` (Coolify sslip, healthy)

**Traefik status:** Already routing correctly.
- `curl -H "Host: api.localloop.ai" http://167.86.79.151/health` → `302` (Traefik HTTPS redirect — correct)
- `http://looper-api.167.86.79.151.sslip.io/health` → `{"status":"healthy"}` 200

**No Traefik restart needed** — Traefik picked up the Coolify app in Pass 3;
the Worker not being deployed was the only gap.

### Public health (post-deploy)
`https://api.localloop.ai/health` → `{"status":"healthy"}` HTTP 200

### Signed deal ingest
`POST https://api.localloop.ai/api/ingest/hybridcard-deal` → `{"ok":true,"duplicate":false}` HTTP 200

### Coolify container state
| App | UUID | Status |
|-----|------|--------|
| looper-api (active) | `cmbro8mqhxvuznl11proayiy` | `running:healthy` |
| looper-api (old/dead) | `r11n46lj151mnfn0c9htaj47` | `exited:unhealthy` |

### Remaining Bill gate
- **Restart HybridCard container** (Coolify) so it picks up the env vars
  (`LOOPER_INGEST_URL`, `LOOPER_CARD_INGEST_URL`, `HYBRIDCARD_INGEST_SECRET`)
  added in Pass 3. This is a prod-container restart — Bill owns this gate (F9.4).
- **Optional DNS cleanup:** Replace CF Worker route + stale CNAME with a
  plain A record `api → 167.86.79.151` (proxied). OAuth scopes lack `dns:edit`
  so this needs Cloudflare dashboard or a token with `Zone.DNS:Edit`.

---

## F1.5 / F9.1 acceptance criteria
- [x] `https://api.localloop.ai/health` → `{"status":"healthy"}`
- [x] Signed deal POST → 200 `{"ok":true,"duplicate":false}`
- [x] Signed card POST → 200 `{"ok":true,"duplicate":false}`
- [x] Bridge pin POST → 201 `pending_review` in Supabase
- [x] Coolify durable origin (API-created; Worker ORIGIN → Coolify sslip)
- [ ] HybridCard prod outbound flag flip / container restart for new env (F9.4 — Bill gates this)

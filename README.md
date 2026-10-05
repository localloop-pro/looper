# LOOPER — Local Connection Agent

Looper is the LocalLoop ecosystem's community-discovery and agent layer. It provides a FastAPI search/bridge service, a browser-embeddable Jarvis map experience, an Electron voice companion, and an optional TypeDB-backed knowledge layer.

Read [`SEED.md`](SEED.md), [`.SEED/decisions.md`](.SEED/decisions.md), [`.SEED/gotchas.md`](.SEED/gotchas.md), and [`AGENTS.md`](AGENTS.md) before changing the system. The cross-repository delivery sequence is maintained in [`plans/IMPLEMENTATION_PLAN.md`](plans/IMPLEMENTATION_PLAN.md).

## Repository map

```text
backend/       FastAPI API, SQLite persistence, bridge ingest, identity, tests
brain/         Optional TypeDB schemas, migrations, and query layer
looper-bot/    Electron + React + Vite voice companion
web/           Embeddable widget and Jarvis map modules/demos
training/      Privacy-filtered training export and optional ML tooling
tools/         Operator and news/audio utilities
workers/       Edge/API proxy workers
plans/         Master plan, feature plans, completion state, and evidence
data/          Local runtime data (not source-controlled)
```

## Backend quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
python main.py
```

The default API is `http://localhost:8000`. If TypeDB or another service already uses that port:

```bash
LOOPER_PORT=8010 python main.py
```

Check the service with:

```bash
curl http://localhost:8000/health
open http://localhost:8000/docs
```

Use [`.env.example`](.env.example) as the configuration reference. The backend reads the process environment; export the required variables (or source a private local env file in your shell) before startup. Keep bridge secrets, TypeDB credentials, and production values out of source control.

## Docker / Coolify

The default compose stack builds `backend/Dockerfile`, persists SQLite and the bounded KNS cache in the `looper-data` volume, and publishes the API on `LOOPER_PORT`:

```bash
docker compose up -d --build
curl http://localhost:8000/health
```

For a host port of 8010:

```bash
LOOPER_PORT=8010 docker compose up -d --build
curl http://localhost:8010/health
```

## Looper desktop companion

```bash
cd looper-bot
npm install
npm run dev
```

The app uses OpenAI Realtime over WebRTC and can call Looper/LocalLoop tools. Configure `OPENAI_API_KEY`, `LOOPER_API_BASE`, and `LOCALLOOP_MAP_URL` in `looper-bot/.env.local` as needed.

Useful checks:

```bash
npm run typecheck
npm test
npm run build
```

## Jarvis map demo

With the backend running, open `/demo` to exercise the animated map agent, category/search grammar, and typed fallback. Voice support depends on the browser; typed commands remain available without microphone access.

```bash
cd backend
python seed.py
python main.py
# open http://localhost:8000/demo
```

The reusable browser modules live in `web/jarvis/`. Deep links use query parameters such as `/?cat=Food&q=coffee&fly=151.2743,-33.8908,16`.

## API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/api/onboard` | User onboarding and join-code creation |
| `GET` | `/api/code/{code}` | Validate a join code |
| `GET` | `/api/search` | Community business/service search |
| `GET` | `/api/discover` | Suburb/category discovery |
| `GET` | `/api/businesses` | Browse businesses by category/location |
| `POST` | `/api/reviews` | Submit a review |
| `GET` | `/api/reviews/{business_id}` | Read business reviews |
| `POST` | `/api/pins` | Create a map pin |
| `GET` | `/api/pins` | Read nearby map pins |
| `POST` | `/api/ingest/hybridcard-deal` | HMAC-verified HybridCard deal ingest |
| `POST` | `/api/ingest/hybridcard-card` | HMAC-verified HybridCard card ingest |
| `GET` | `/api/ingest/status` | Aggregate bridge status without PII |
| `GET` | `/api/identity/domains` | Verified allowlisted KNS identities |
| `GET` | `/api/identity/health` | KNS freshness/mismatch health |
| `GET` | `/demo` | Jarvis voice-map demo |

```bash
node web/tests/voice-command-router.test.js      # 46 grammar unit tests
# full headless flow (needs playwright):
cd web && python3 -m http.server 8088 &
node tests/jarvis-smoke.playwright.js
```

### Embedding on the live map (llx11) — one script block

`index.html` is sacred (surgical edits only), so integration is four script
tags + one init call, e.g. right before `</body>`:

```html
<script src="https://api.localloop.ai/web/jarvis/voice-command-router.js"></script>
<script src="https://api.localloop.ai/web/jarvis/looper-map-bus.js"></script>
<script src="https://api.localloop.ai/web/jarvis/looper-face.js"></script>
<script src="https://api.localloop.ai/web/jarvis/looper-jarvis.js"></script>
<script>
  LooperJarvis.init({
    map: window.localloopMap,            // the existing Mapbox map
    markerLib: window.mapboxgl,
    apiBase: window.LocalLoopConfig.looperApi,
    district: "Bondi",
    onCategory: (cat) => { /* sync the site's category filter here */ },
  });
</script>
```

Deep links work out of the box: `/?cat=Food&q=coffee&fly=151.2743,-33.8908,16`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/onboard` | User onboarding (name + mobile + interest). 403 unless `LOOPER_PUBLIC_WRITES=true` |
| GET  | `/api/search?q=&lat=&lng=&radius=` | Search businesses by query |
| GET  | `/api/discover?suburb=&category=&radius_km=` | Suburb discovery (graph-ready, `engine: fallback` today) |
| GET  | `/api/businesses?category=&lat=&lng=` | List businesses by category |
| POST | `/api/reviews` | Submit a review (`verified_visit` always false). 403 unless `LOOPER_PUBLIC_WRITES=true` |
| GET  | `/api/reviews/{business_id}?limit=` | Get reviews for a business. 404 for an unknown business; `limit` 1–50 (default 10) |
| POST | `/api/pins` | Add a map pin. 403 unless `LOOPER_PUBLIC_WRITES=true` |
| GET  | `/api/pins?lat=&lng=&radius=` | Get pins in area |
| GET  | `/api/tourist-info` | Tourist-specific info |
| POST | `/api/ingest/hybridcard-deal` | BRIDGE-CONTRACT-v1 deal receiver (HMAC) |
| POST | `/api/ingest/hybridcard-card` | BRIDGE-CONTRACT-v1 card receiver (HMAC) |
| GET  | `/api/ingest/status` | Read-only bridge cockpit (counts + recent events) |
| GET  | `/api/identity/domains` | Read-only verified organization KNS identities |
| GET  | `/api/identity/domains/{domain}` | One allowlisted organization KNS identity |
| GET  | `/api/identity/health` | Operator freshness/mismatch health summary |
| GET  | `/demo` | Jarvis voice-map demo (serves `web/jarvis/`) |

### Kaspa organization identity operations

The API verifies only the configured `localloop.kas` and `qikflo.kas` mainnet
records. It never holds a wallet key and never grants authorization. Production
defaults are `KNS_API_BASE_URL=https://api.knsdomains.org/mainnet`, a one-hour
fresh TTL, and a 24-hour bounded stale window. A `mismatch` is a security event:
the UI removes verified wording immediately. `stale` is display-only. Monitor
`GET /api/identity/health`; investigate any `degraded` response before changing
the configured owner or cache window. The cache defaults to
`backend/data/kaspa_identity_cache.json` for a plain checkout; in Docker/Coolify
`docker-compose.yml` sets `KASPA_IDENTITY_CACHE_PATH=/app/data/kaspa_identity_cache.json`
so it lives on the `looper-data` volume and survives redeploys. Cache writes are
best-effort (an unwritable path logs a warning and still returns `fresh`); each
entry is fingerprinted to the provider URL and expected identity, and a
`mismatch` tombstones the entry so a later outage can never report `stale`.

#### Run and verify (copy-paste)

Local checkout — start the API on **8010** (port 8000 is taken by the local
TypeDB server on Bill's machine; see `.SEED/gotchas.md`), then hit the three
identity routes:

```bash
cd backend && LOOPER_PORT=8010 python main.py        # serves http://localhost:8010
```

```bash
curl -s http://localhost:8010/api/identity/domains | python3 -m json.tool
```

Expected: `{"domains": [ ... ]}` with two records, `localloop.kas` and
`qikflo.kas`, each carrying `verificationState` = `fresh` on a machine with
internet access to `api.knsdomains.org` (`unavailable` if you are offline —
that is the bounded fail-closed answer, not an error).

```bash
curl -s http://localhost:8010/api/identity/domains/localloop.kas | python3 -m json.tool
```

Expected: one record whose `assetId` ends in `i0`, `transactionId` equals the
`assetId` without that suffix, `ownerAddress` starts with `kaspa:qrs4ss39…`, and
`explorerUrl` points at `https://kas.fyi/transaction/…`. An unknown domain
(`/api/identity/domains/attacker.kas`) returns **404**.

```bash
curl -s http://localhost:8010/api/identity/health | python3 -m json.tool
```

Expected: `{"status": "healthy", "provider": "kns-mainnet-v1", "domains":
{"localloop.kas": "fresh", "qikflo.kas": "fresh"}}`. Any `degraded` status
names the domain that is `stale`, `unavailable`, or `mismatch` — investigate
`mismatch` immediately (it means the on-chain record no longer matches the
configured identity).

Docker / Coolify deployment — same checks against the deployed host:

```bash
LOOPER_PORT=8010 docker compose up -d --build && sleep 5 && curl -s http://localhost:8010/api/identity/health
```

(`LOOPER_PORT` is the host port mapping in `docker-compose.yml`; the container
itself always listens on 8000.)

```bash
curl -s https://api.localloop.ai/api/identity/health | python3 -m json.tool
```

Expected: identical `healthy` payload. The cache file lives at
`/app/data/kaspa_identity_cache.json` inside the `looper-data` volume
(`docker compose exec looper-api cat /app/data/kaspa_identity_cache.json`
shows two fingerprinted entries after the first successful check).

Offline / regression proof without network access:

```bash
cd backend && .venv/bin/python -m pytest tests/test_kaspa_identity.py -q
```

Expected: all tests pass (they use an in-process mock provider).

## Verification

```bash
cd backend
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

cd ../looper-bot
npm run typecheck
npm test
npm run build

cd ../
node web/tests/voice-command-router.test.js
node web/tests/kaspa-identity.test.js
```

TypeDB tests and services are optional unless the active task enables that lane. Install [`requirements-brain.txt`](requirements-brain.txt) and follow [`brain/README.md`](brain/README.md) before enabling it.

## Safety invariants

- Rank only with verifiable signals such as proximity, recency, and review evidence. Never sell ranking or declare a business “best.”
- Return multiple useful options where possible; discounts may affect marker presentation, not rank.
- Bridge payloads are public-safe: never send names, mobiles, emails, VIP identity, or other PII.
- `BRIDGE-CONTRACT-v1` payload shapes are frozen. Receivers adapt without silently changing sender contracts.
- Bots write through audited gateway endpoints with idempotency and approval gates; they do not write directly to production databases.
- KNS verification is read-only identity evidence, not authentication or authorization. A mismatch removes verified wording immediately.
- Payments, auth, deployment, migration, customer-data, and real-message changes require owner approval.

### Anti-bias rules

1. NEVER rank by anything other than verifiable data (review count, recency)
2. NEVER declare any business "the best"
3. ALWAYS show multiple options
4. ALWAYS attribute reviews to real users
5. NEVER accept sponsorship or paid placement

## Ecosystem links

- LocalLoop public map: `../localloop.pro/localloop.pro-main/llx11/localloop.pro-main/`
- HybridCard product: `../hybridcard.ai/new-card/`
- Shared HybridCard/Looper skill hub: [`../hybridcard.ai/looper/skills/SKILLS.md`](../hybridcard.ai/looper/skills/SKILLS.md)
- Bridge and rollout status: [`plans/COMPLETION_STATUS.md`](plans/COMPLETION_STATUS.md)

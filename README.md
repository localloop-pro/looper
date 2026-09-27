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

FastAPI's `/docs` is the current endpoint-level reference.

## Verification

```bash
cd backend
pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

cd ../looper-bot
npm run typecheck
npm test
npm run build

cd ../
node web/tests/voice-command-router.test.js
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

## Ecosystem links

- LocalLoop public map: `../localloop.pro/localloop.pro-main/llx11/localloop.pro-main/`
- HybridCard product: `../hybridcard.ai/new-card/`
- Shared HybridCard/Looper skill hub: [`../hybridcard.ai/looper/skills/SKILLS.md`](../hybridcard.ai/looper/skills/SKILLS.md)
- Bridge and rollout status: [`plans/COMPLETION_STATUS.md`](plans/COMPLETION_STATUS.md)

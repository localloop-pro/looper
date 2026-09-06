# LOOPER — Local Connection Agent

Community connection agent for LocalLoop. Connects people with businesses and services in their local area via Telegram and web search bar. Powered by genuine community reviews.

## Architecture

```
looper/
├── backend/           # FastAPI service
│   ├── main.py        # API entry point
│   ├── db.py          # SQLAlchemy + SQLite
│   ├── models.py      # Database models
│   ├── schemas.py     # Pydantic schemas
│   ├── routes/        # API routes
│   │   ├── users.py   # User onboarding + codes
│   │   ├── search.py  # Business/service search
│   │   └── map.py     # Map pins and layers
│   ├── services/      # Business logic
│   │   ├── review.py  # Review aggregation + ranking
│   │   ├── matching.py # User-to-business matching
│   │   └── training.py # Training data export
│   └── requirements.txt
├── hermes/            # Hermes agent integration
│   └── SOUL.md        # LOOPER personality (symlink)
├── training/          # Hugging Face pipeline
│   ├── export.py      # Export training_log to HF format
│   ├── finetune.py    # Fine-tune Mistral/Llama on local data
│   └── config.yaml    # Training config
├── web/               # Search bar widget
│   ├── looper-widget.js   # Embeddable chat widget
│   ├── looper-widget.css
│   └── index.html     # Demo page
├── data/              # Local data (gitignored)
│   └── looper.db      # SQLite database
└── README.md
```

## Quick Start

```bash
cd backend
pip install -r requirements.txt
python main.py  # Starts on http://localhost:8000
```

## Run the ecosystem locally

Verified commands for bringing up all three systems on one machine
(paths for 2 and 3 are sibling repos, relative to this repo's parent).

### 1. Looper backend (this repo)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # first time only
pip install -r requirements.txt
python seed.py        # → ✅ Seeded: 20 businesses, 11 reviews, 1 users
python main.py        # serves http://localhost:8000

# check:
curl http://localhost:8000/health     # {"status":"healthy"}
open http://localhost:8000/docs       # all routes listed
```

> Port 8000 busy? (a local TypeDB server also defaults to 8000) — run
> `LOOPER_PORT=8010 python main.py` and check `localhost:8010/health`.

### 2. llx11 map site (sibling repo)

```bash
cd "../localloop.pro/localloop.pro-main/llx11/localloop.pro-main"
npm ci && npm start   # static serve on http://localhost:3000
# check:
curl http://localhost:3000/health.json   # {"status":"ok",...}
```

Needs `MAPBOX_TOKEN` in its `.env` for the map itself to render
(`npm run prestart` injects `assets/js/env.js`); `health.json` works
without it.

### 3. HybridCard new-card (sibling repo)

```bash
cd "../hybridcard.ai/new-card"
npm ci && npm run dev   # http://localhost:3000 (stop llx11 first — same port)
# check:
curl http://localhost:3000/api/health    # {"ok":true,"service":"hybridcard",...}
```

Needs a local MongoDB (`mongod` on 27017) and `MONGODB_URI` in `.env.local`.

### 4. Looper-bot desktop companion (optional)

```bash
cd looper-bot
npm ci && npm run dev   # Electron app; needs OPENAI_API_KEY in looper-bot/.env.local
```

With the backend running, Looper can also answer local-business questions
(`localloop_search`), open the live map deep-linked
(`localloop_open_map` → `https://localloop.ai/?cat=Food&fly=…`), and report
the HybridCard bridge status (`localloop_bridge_status`). Optional env in
`looper-bot/.env.local`: `LOOPER_API_BASE` (default `http://localhost:8000`),
`LOCALLOOP_MAP_URL` (default `https://localloop.ai`).

## Jarvis map demo (talk to Looper ON the map)

The `web/jarvis/` modules put the animated Looper face on any
Mapbox-GL-compatible map with full voice control (ported from the old
explore-local build, bugs fixed). Try it locally — no keys needed:

```bash
cd backend
pip install -r requirements.txt
python seed.py          # once, seeds Bondi businesses
python main.py          # serves API + demo
# open http://localhost:8000/demo in Chrome (or Safari)
# (on Bill's machine: LOOPER_PORT=8010 python main.py → http://localhost:8010/demo)
```

Tap the face and say: *"find me a café"*, *"any deals near me"*,
*"take me to Bronte"*, *"who can help me with my garden"*, *"zoom in"*,
*"reset the map"*. Or press **🎙 Hey Looper** for hands-free mode — the mic
stays open and only utterances starting with "Hey Looper …" act (say "stop"
to interrupt). Voice needs Chrome/Edge/Safari (Firefox falls back to typed
input). Category chips fire the same grammar as the voice.

Every search is logged to `training_log` (query + intent + anonymous
session, emails/mobiles scrubbed) so `python training/export.py` now has
real data.

Verify without a mic or backend:

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
| POST | `/api/onboard` | User onboarding (name + mobile + interest) |
| GET  | `/api/code/{code}` | Validate 6-digit join code |
| GET  | `/api/search?q=&lat=&lng=&radius=` | Search businesses by query |
| GET  | `/api/discover?suburb=&category=&radius_km=` | Suburb discovery (graph-ready, `engine: fallback` today) |
| GET  | `/api/businesses?category=&lat=&lng=` | List businesses by category |
| POST | `/api/reviews` | Submit a review |
| GET  | `/api/reviews/{business_id}` | Get reviews for a business |
| POST | `/api/pins` | Add a map pin |
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

Local checkout — start the API the usual way, then hit the three identity routes:

```bash
cd backend && python main.py        # serves http://localhost:8000 (see "Looper backend" above)
```

```bash
curl -s http://localhost:8000/api/identity/domains | python3 -m json.tool
```

Expected: `{"domains": [ ... ]}` with two records, `localloop.kas` and
`qikflo.kas`, each carrying `verificationState` = `fresh` on a machine with
internet access to `api.knsdomains.org` (`unavailable` if you are offline —
that is the bounded fail-closed answer, not an error).

```bash
curl -s http://localhost:8000/api/identity/domains/localloop.kas | python3 -m json.tool
```

Expected: one record whose `assetId` ends in `i0`, `transactionId` equals the
`assetId` without that suffix, `ownerAddress` starts with `kaspa:qrs4ss39…`, and
`explorerUrl` points at `https://kas.fyi/transaction/…`. An unknown domain
(`/api/identity/domains/attacker.kas`) returns **404**.

```bash
curl -s http://localhost:8000/api/identity/health | python3 -m json.tool
```

Expected: `{"status": "healthy", "provider": "kns-mainnet-v1", "domains":
{"localloop.kas": "fresh", "qikflo.kas": "fresh"}}`. Any `degraded` status
names the domain that is `stale`, `unavailable`, or `mismatch` — investigate
`mismatch` immediately (it means the on-chain record no longer matches the
configured identity).

Docker / Coolify deployment — same checks against the deployed host:

```bash
docker compose up -d --build && sleep 5 && curl -s http://localhost:8000/api/identity/health
```

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

## Database Schema

See `backend/models.py` for full schema:

- **users** — first_name, mobile, join_code, user_type, interest_category
- **businesses** — name, category, address, lat/lng, hybrid_card_id
- **reviews** — business_id, user_id, rating, text, verified
- **map_pins** — user_id, type, title, desc, lat/lng, expires
- **training_log** — query, response, user_id, feedback

## Anti-Bias Rules

1. NEVER rank by anything other than verifiable data (review count, recency)
2. NEVER declare any business "the best"
3. ALWAYS show multiple options
4. ALWAYS attribute reviews to real users
5. NEVER accept sponsorship or paid placement

## HybridCard agent skills

VIP checkout, member pass, and TypeDB bridge skills live in the HybridCard Looper hub:

- **Skills index:** [`../hybridcard.ai/looper/skills/SKILLS.md`](../hybridcard.ai/looper/skills/SKILLS.md)
- **VIP checkout:** [`../hybridcard.ai/looper/skills/hybridcard-vip-checkout/SKILL.md`](../hybridcard.ai/looper/skills/hybridcard-vip-checkout/SKILL.md)

`businesses.hybrid_card_id` links this service to HybridCard slugs for search and checkout context.

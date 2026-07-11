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

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/onboard` | User onboarding (name + mobile + interest) |
| GET  | `/api/code/{code}` | Validate 6-digit join code |
| GET  | `/api/search?q=&lat=&lng=&radius=` | Search businesses by query |
| GET  | `/api/businesses?category=&lat=&lng=` | List businesses by category |
| POST | `/api/reviews` | Submit a review |
| GET  | `/api/reviews/{business_id}` | Get reviews for a business |
| POST | `/api/pins` | Add a map pin |
| GET  | `/api/pins?lat=&lng=&radius=` | Get pins in area |
| GET  | `/api/tourist-info` | Tourist-specific info |

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
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
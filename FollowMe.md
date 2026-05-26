# 📌 Project: LOOPER

**LocalLoop community connection agent** — connects people with businesses and services in their local area via Telegram and web search bar. Powered by genuine community reviews, never by sponsorship.

- **Repo:** localloop-pro/looper
- **Hermes Profile:** ~/.hermes/profiles/looper/
- **Wrapper:** `looper` CLI
- **Owner:** QIKFLO Pty Ltd (Bill)

---

## 📍 Status: **phase-1-ready**

v0.1 backend is built, tested, and pushed. Awaiting Telegram bot token to go live.

---

## 🔒 Lock: **none**

---

## 🤖 Active Agent: **Luna** (setup complete)

| Field | Value |
|-------|-------|
| **Built** | 2026-05-26 |
| **Phase** | 1 — Profile + Backend complete |
| **Blocker** | Needs Telegram bot token from Bill |

---

## 🎚️ Autonomy Level: **confirm-first**

---

## 📦 What's Built

| Component | Status | Details |
|-----------|--------|---------|
| Hermes Profile | ✅ | `~/.hermes/profiles/looper/` — isolated config, skills, sessions |
| GitHub Repo | ✅ | `localloop-pro/looper` — 3 commits, main branch |
| Backend API | ✅ | FastAPI on port 8000 — health, search, onboard, reviews, map, pins |
| Database | ✅ | SQLite — 20 Bondi businesses + 11 reviews seeded |
| Search Engine | ✅ | Tokenized + relevance-scored. Anti-bias: never picks favorites |
| Onboarding Flow | ✅ | Name + mobile → 6-digit code → map + recommendations |
| SOUL.md | ✅ | Full personality, 4 conversation flows, anti-bias rules |
| Web Widget | ✅ | `web/looper-widget.js` — embeddable chat widget |
| Training Pipeline | ✅ | `training/export.py` — exports to JSONL + HF datasets |

## 🔜 Awaiting

| Item | Owner | Notes |
|------|-------|-------|
| Telegram bot token | Bill | Create @looper_bot via @BotFather |
| Gateway launch | Luna | `looper gateway run` after token set |
| Widget integration | Luna | Embed on localloop.pro-main |
| Facebook data pipeline | Future | 150k Bondi Local Loop members |
| HuggingFace fine-tuning | Future | After training data accumulates |

---

## 📝 Session Log

| # | Timestamp | Agent | Action |
|---|-----------|-------|--------|
| 1 | 2026-05-26 | Luna | Created profile, repo, backend (FastAPI+SQLite), seeded 20 Bondi businesses + 11 reviews, built tokenized anti-bias search, onboarding flow, web widget, training pipeline |

---

## ⚡ Quick Commands

```bash
# Start backend
cd /mnt/c/Users/bondi/Documents/GITHUB_main/Projects/looper/backend
pip install -r requirements.txt
python main.py  # → http://localhost:8000

# Test search
curl "http://localhost:8000/api/search?q=café&lat=-33.8908&lng=151.2748"

# Onboarding test
curl -X POST http://localhost:8000/api/onboard \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Test","mobile_number":"0412345678","interest_category":"cafés"}'

# Seed DB
python seed.py

# Smoke test agent
looper -z "reply with only the text: LOOPER_ONLINE"
```
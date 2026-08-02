# BUG_SOLUTIONS — looper

Patterns that already bit us. Check here before inventing a new fix.

## HybridCard local card URL stripped / rewritten to `*.hybridcard.ai`

**Symptom:** Jarvis "View card →" opens `https://bondi-cafe.hybridcard.ai`
("no available server") instead of `http://localhost:3000/c/bondi-cafe`
while HybridCard is running locally.

**Root cause:** `/api/search` and `/api/discover` only treated
`biz.website` as a card URL when it contained `.hybridcard.ai`. Local
HybridCard emits path URLs via `buildClaimUrl()` (`APP_URL` + `/c/{slug}`).

**Fix:** `resolve_card_url()` in `backend/routes/search.py` — pass through
active `Deal.public_card_url` or bridge-set `Business.website` for any host.
Ingest already stores the payload URL as-is (no rewrite). Jarvis/map-bus
already use `r.card_url` without inventing a slug.

**Verify after HybridCard re-ingest:**

```bash
cd backend && python -m pytest tests/test_search_voice.py tests/test_ingest_card.py tests/test_ingest_deal.py -q
curl -s "http://localhost:8010/api/search?q=Bondi%20Cafe" | python3 -m json.tool
# expect card_url like http://localhost:3000/c/bondi-cafe
```

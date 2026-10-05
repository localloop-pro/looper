# LOOPER Tools

Standalone scripts run as Coolify Scheduled Tasks.

## `jarvis-sync-check.js` (looper#39)

Read-only drift check for the Jarvis voice router. The live map
(localloop.pro-main) ships its own copy at
`assets/js/jarvis/voice-command-router.js`; router changes land here first.

```bash
node tools/jarvis-sync-check.js                              # Looper's copy vs /api/discover
node tools/jarvis-sync-check.js --map ../localloop.pro-main  # also check the map's copy
```

Checks: `SUBURBS` keys + lat/lng equal `SUBURB_COORDS` in
`backend/routes/discover.py`; the router exports `WAKE_RE` / `WAKE_STRICT_RE`;
the map's `looper-jarvis.js` reads them; a fixed phrase list (wake mishears,
barge-in, suburbs) routes the same as Looper. Exit 0 = in sync, 1 = drift,
2 = bad path. Tests: `node web/tests/jarvis-sync.test.js`.

## `check_skill_citations.py` (looper#89)

Read-only check that every file:line citation in a skills registry entry
(`.SEED/skills/<archetype>/*.md`) resolves at the commit the entry pins.
Needs local clones of the other two repos; never fetches or writes.

```bash
python3 tools/check_skill_citations.py \
  --repo map=../localloop.pro-main --repo cards=../hybridcard-v2
```

Exit 0 = all resolve, 1 = a citation is missing or blank, 2 = a cited repo
or pinned commit isn't available locally. Tests:
`backend/tests/test_skill_citations.py`.

## `news_audio_worker.py` (F6.1)

Converts news posts (Supabase `news_post` table) to spoken MP3 using
OpenAI TTS, uploads to Supabase Storage, and sets `audio_url`.

The existing podcast player on localloop.ai already prefers `audio_url`
over browser TTS — no client changes needed.

### Install

```bash
pip install -r tools/requirements.txt
```

The API (`backend/requirements.txt`) does not include openai or supabase.

### Env vars

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `SUPABASE_URL` | ✓ | — | e.g. `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | ✓ | — | Service-role key (NEVER anon) |
| `NEWS_TTS_PROVIDER` | — | `openai` | TTS provider |
| `NEWS_TTS_API_KEY` | ✓ | `$OPENAI_API_KEY` | API key for TTS |
| `NEWS_AUDIO_BUCKET` | — | `news-audio` | Supabase Storage bucket |
| `NEWS_AUDIO_VOICE` | — | `alloy` | OpenAI voice name |
| `NEWS_MAX_CHARS` | — | `1200` | Truncate input to this length |
| `NEWS_AUDIO_BATCH` | — | `5` | Posts per run (time-budget) |

### Supabase bucket setup (once)

Create a **public-read** bucket named `news-audio` in Supabase Storage:

```sql
-- In Supabase SQL editor:
INSERT INTO storage.buckets (id, name, public) VALUES ('news-audio', 'news-audio', true);
```

Or via the dashboard: Storage → New bucket → name `news-audio` → Public.

### Run manually

```bash
SUPABASE_URL=https://xxxx.supabase.co \
SUPABASE_SERVICE_KEY=<service-key> \
OPENAI_API_KEY=<openai-key> \
python tools/news_audio_worker.py
```

### Coolify Scheduled Task

Schedule: `*/10 * * * *`  
Command: `python /app/looper/tools/news_audio_worker.py`

### Idempotency

- Rows with `audio_url` already set are skipped.
- Rows that previously failed (have `payload.audio_error`) are skipped.
- Delete `audio_error` from payload to retry a failed row.
- Re-running always overwrites the Storage MP3 (upsert) but only updates
  `audio_url` on the first successful run (the skip check above).

## `bench_read_paths.py` (issue #8)

Local p50/p95 + error-rate harness for `/api/search` and `/api/discover`
(E1 method: 20 warmup, 100 sequential, 200 at 10 workers). Stdlib only.
Point it at a local server on a throwaway DB — never at production.

```bash
python3 tools/bench_read_paths.py http://127.0.0.1:8010
```

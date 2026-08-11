# LOOPER Tools

Standalone scripts run as Coolify Scheduled Tasks.

## `news_audio_worker.py` (F6.1)

Converts news posts (Supabase `news_post` table) to spoken MP3 using
OpenAI TTS, uploads to Supabase Storage, and sets `audio_url`.

The existing podcast player on localloop.ai already prefers `audio_url`
over browser TTS — no client changes needed.

### Install

```bash
pip install supabase openai
```

### Env vars

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `SUPABASE_URL` | ✓ | — | e.g. `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | ✓ | — | Service-role key (NEVER anon) |
| `NEWS_TTS_PROVIDER` | — | `openai` | TTS provider |
| `NEWS_TTS_API_KEY` | ✓ | `$OPENAI_API_KEY` | API key for TTS |
| `NEWS_AUDIO_BUCKET` | — | `news-audio` | Supabase Storage bucket |
| `NEWS_AUDIO_VOICE` | — | `alloy` | OpenAI voice name |
| `NEWS_MAX_CHARS` | — | `1800` | Truncate input to this length |
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
Command: `python tools/news_audio_worker.py`

### Idempotency

- Rows with `audio_url` already set are skipped.
- Rows that previously failed (have `payload.audio_error`) are skipped.
- Delete `audio_error` from payload to retry a failed row.
- Re-running always overwrites the Storage MP3 (upsert) but only updates
  `audio_url` on the first successful run (the skip check above).

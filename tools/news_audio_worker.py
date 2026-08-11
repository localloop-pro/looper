"""F6.1 — News audio worker.

Finds news_post rows with audio_url IS NULL, generates speech via the
configured TTS provider (default: OpenAI tts-1), uploads the MP3 to a
Supabase Storage bucket, and updates audio_url.

Designed to run as a Coolify Scheduled Task every 10 minutes:
    python tools/news_audio_worker.py

Environment:
    SUPABASE_URL           — e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY   — service-role key (NEVER anon — server-side only)
    NEWS_TTS_PROVIDER      — "openai" (default) or future providers
    NEWS_TTS_API_KEY       — API key for the TTS provider
    NEWS_AUDIO_BUCKET      — Supabase Storage bucket (default: news-audio)
    NEWS_AUDIO_VOICE       — OpenAI voice (default: alloy)
    NEWS_MAX_CHARS         — truncate input to this many chars (default: 1800)

Anti-bias / public-safe notes:
    - Audio content is derived from news_post.title + body only.
    - No PII is read or written.
    - audio_error is set in payload on failure; the row is skipped next run.

Install: pip install supabase openai
"""
from __future__ import annotations

import io
import logging
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
TTS_PROVIDER = os.getenv("NEWS_TTS_PROVIDER", "openai")
TTS_API_KEY = os.getenv("NEWS_TTS_API_KEY") or os.getenv("OPENAI_API_KEY", "")
AUDIO_BUCKET = os.getenv("NEWS_AUDIO_BUCKET", "news-audio")
AUDIO_VOICE = os.getenv("NEWS_AUDIO_VOICE", "alloy")
MAX_CHARS = int(os.getenv("NEWS_MAX_CHARS", "1800"))

# Coolify batch: process at most N posts per run to stay within 10-min window
BATCH_SIZE = int(os.getenv("NEWS_AUDIO_BATCH", "5"))


def _check_env() -> bool:
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY") if not os.getenv(k)]
    if TTS_PROVIDER == "openai" and not TTS_API_KEY:
        missing.append("NEWS_TTS_API_KEY / OPENAI_API_KEY")
    if missing:
        logger.error("Missing env vars: %s", ", ".join(missing))
        return False
    return True


def _strip_markup(text: str) -> str:
    """Remove markdown links, headers, URLs, and HTML tags for TTS input."""
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)   # [label](url) → label
    text = re.sub(r'https?://\S+', '', text)                 # bare URLs
    text = re.sub(r'<[^>]+>', '', text)                      # HTML tags
    text = re.sub(r'#+\s?', '', text)                        # ## headers
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)   # *bold*
    return text.strip()


def _build_tts_text(row: dict) -> str:
    """Build the spoken text for a news post."""
    district = row.get("district_slug") or "Local Loop"
    title = (row.get("title") or "").strip()
    body = _strip_markup(row.get("body") or "")
    date_str = ""
    try:
        dt = datetime.fromisoformat((row.get("created_at") or "").replace("Z", "+00:00"))
        date_str = dt.strftime("%A %d %B %Y")
    except Exception:
        pass

    intro = f"Local Loop {district.replace('-', ' ').title()} news"
    if date_str:
        intro += f", {date_str}"
    intro += ". "

    text = intro + title + ". " + body
    return text[:MAX_CHARS]


def _generate_audio_openai(text: str, api_key: str) -> bytes:
    """Call OpenAI TTS and return MP3 bytes."""
    from openai import OpenAI  # type: ignore[import]
    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model="tts-1",
        voice=AUDIO_VOICE,
        input=text,
        response_format="mp3",
    )
    buf = io.BytesIO()
    for chunk in response.iter_bytes():
        buf.write(chunk)
    return buf.getvalue()


def _generate_audio(text: str) -> bytes:
    if TTS_PROVIDER == "openai":
        return _generate_audio_openai(text, TTS_API_KEY)
    raise ValueError(f"Unknown TTS provider: {TTS_PROVIDER}")


def _upload_audio(supabase_client, post_id: str, mp3_bytes: bytes) -> str:
    """Upload MP3 to Supabase Storage and return the public URL."""
    path = f"{post_id}.mp3"
    storage = supabase_client.storage.from_(AUDIO_BUCKET)
    # upsert=True overwrites on re-run (idempotent)
    storage.upload(path=path, file=mp3_bytes, file_options={
        "content-type": "audio/mpeg",
        "upsert": "true",
    })
    public_url = storage.get_public_url(path)
    return public_url


def _set_audio_url(supabase_client, post_id: str, audio_url: str) -> None:
    (supabase_client.table("news_post")
     .update({"audio_url": audio_url})
     .eq("id", post_id)
     .execute())


def _mark_error(supabase_client, post_id: str, error: str) -> None:
    (supabase_client.table("news_post")
     .update({"payload": {"audio_error": error[:200]}})
     .eq("id", post_id)
     .execute())


def run() -> None:
    if not _check_env():
        sys.exit(1)

    try:
        from supabase import create_client  # type: ignore[import]
    except ImportError:
        logger.error("supabase not installed. Run: pip install supabase")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Fetch posts that need audio (audio_url IS NULL, no audio_error)
    response = (sb.table("news_post")
                .select("id, title, body, created_at, district_slug, payload")
                .is_("audio_url", "null")
                .limit(BATCH_SIZE)
                .execute())

    posts = response.data or []
    # Skip any post already marked with an audio_error
    posts = [p for p in posts if not (p.get("payload") or {}).get("audio_error")]

    if not posts:
        logger.info("No news posts need audio — nothing to do")
        return

    logger.info("Processing %d news post(s)", len(posts))

    for post in posts:
        post_id = post["id"]
        try:
            tts_text = _build_tts_text(post)
            logger.info("  [%s] generating audio (%d chars) ...", post_id, len(tts_text))
            mp3_bytes = _generate_audio(tts_text)
            audio_url = _upload_audio(sb, post_id, mp3_bytes)
            _set_audio_url(sb, post_id, audio_url)
            logger.info("  [%s] done → %s", post_id, audio_url)
        except Exception as exc:
            logger.error("  [%s] FAILED: %s", post_id, exc)
            try:
                _mark_error(sb, post_id, str(exc))
            except Exception:
                pass


if __name__ == "__main__":
    run()

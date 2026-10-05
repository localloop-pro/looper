- 2026-10-02 (looper#55): `backend/requirements.txt` lists only what the API
  imports. openai, aiosqlite and geopy removed (no import; engine is sync
  `sqlite://`). facebook_pipeline's live Graph call uses `httpx` instead of the
  unlisted `requests`. openai + supabase live in `tools/requirements.txt`; the
  Dockerfile still installs them by default (`WITH_TOOLS=1`) because the Coolify
  news-audio scheduled task runs from the API image — `WITH_TOOLS=0` builds an
  API-only image. `test_runtime_requirements.py` fails if a backend import is
  unlisted or a removed package returns.

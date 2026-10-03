"""F2.5 — self-improving telemetry: log queries into training_log.

Rules (master plan): query, response summary, intent, session_id — NO PII.
Telemetry must NEVER break or block the request that triggered it.
`training/export.py` consumes these rows for the fine-tune loop.
"""
import re

from models import TrainingLog

# Redact before storage — voice transcripts can contain dictated contact
# details ("my email is…"). Business names/categories are public data.
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# AU mobiles as dictated/typed: 04xx xxx xxx, +61 4xx…, with optional
# space/dash separators.
AU_MOBILE_RE = re.compile(r"(?:\+?61|0)[\s-]?4(?:[\s-]?\d){8}")


def scrub_pii(text: str | None) -> str | None:
    if text is None:
        return None
    text = EMAIL_RE.sub("[email]", text)
    text = AU_MOBILE_RE.sub("[mobile]", text)
    return text


# `intent` and `session` are public query params (looper#84): store them only
# when they look like what real callers send, never as free text.
INTENT_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def clean_intent(intent) -> str | None:
    """Short lower-case slug (search, discover, business, voice…), else
    "other". Empty stays None so routes can apply their default."""
    if not intent:
        return None
    slug = str(intent).strip().lower()
    return slug if INTENT_RE.fullmatch(slug) else "other"


def clean_session_id(session_id) -> str | None:
    """Opaque id (letters, digits, _ and -, max 64) that is not an email or
    AU mobile, else None."""
    if not session_id or not isinstance(session_id, str):
        return None
    if not SESSION_ID_RE.fullmatch(session_id):
        return None
    if EMAIL_RE.search(session_id) or AU_MOBILE_RE.search(session_id):
        return None
    return session_id


def log_query(db, query_text: str, intent: str | None = None,
              session_id: str | None = None,
              response_text: str | None = None) -> None:
    """Best-effort append to training_log. Swallows every failure —
    search must keep answering even if telemetry can't write."""
    try:
        db.add(TrainingLog(
            query_text=(scrub_pii(query_text) or "")[:2000],
            response_text=(scrub_pii(response_text) or None),
            intent=clean_intent(intent),
            session_id=clean_session_id(session_id),
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

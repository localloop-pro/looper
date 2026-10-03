"""F2.5 — self-improving telemetry: log queries into training_log.

Rules (master plan): query, response summary, intent, session_id — NO PII.
Telemetry must NEVER break or block the request that triggered it.
`training/export.py` consumes these rows for the fine-tune loop.
"""
import re

from models import TrainingLog
from services.pii import AU_MOBILE_RE, EMAIL_RE, scrub_pii


# `intent` and `session` arrive as public query params (looper#84), so they
# are allow-listed by shape rather than scrubbed: anything that is not a short
# label / opaque id is dropped before storage.
INTENT_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def clean_intent(intent) -> str | None:
    """Lower-cased slug (`search`, `voice`, …), "other" for anything else,
    None when the caller sent nothing."""
    if intent is None:
        return None
    value = str(intent).strip().lower()
    if not value:
        return None
    return value if INTENT_RE.fullmatch(value) else "other"


def clean_session_id(session_id) -> str | None:
    """Opaque id as sent, or None if it is not id-shaped or looks like an
    email / AU mobile."""
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
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

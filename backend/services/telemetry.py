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


def log_query(db, query_text: str, intent: str | None = None,
              session_id: str | None = None,
              response_text: str | None = None) -> None:
    """Best-effort append to training_log. Swallows every failure —
    search must keep answering even if telemetry can't write."""
    try:
        db.add(TrainingLog(
            query_text=(scrub_pii(query_text) or "")[:2000],
            response_text=(scrub_pii(response_text) or None),
            intent=(intent or None) and str(intent)[:100],
            session_id=(session_id or None) and str(session_id)[:100],
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

"""F2.5 — self-improving telemetry: log queries into training_log.

Rules (master plan): query, response summary, intent, session_id — NO PII.
Telemetry must NEVER break or block the request that triggered it.
`training/export.py` consumes these rows for the fine-tune loop.
"""
from models import TrainingLog
from services.pii import scrub_pii


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

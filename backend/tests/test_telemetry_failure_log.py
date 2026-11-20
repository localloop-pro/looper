"""looper#166 — a dropped training_log write must leave one public-safe log
line (exception class only) while log_query still returns normally."""
import logging

from services.telemetry import log_query


class _BoomDb:
    def add(self, obj):
        pass

    def commit(self):
        raise RuntimeError("secret-query-text 0412 345 678 sess-abc123")

    def rollback(self):
        raise ValueError("rollback also failed")


def test_dropped_write_is_logged_without_pii(caplog):
    with caplog.at_level(logging.WARNING):
        log_query(_BoomDb(), "secret-query-text", session_id="sess-abc123",
                  response_text="secret-response")
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "RuntimeError" in text
    for leaked in ("secret-query-text", "secret-response", "sess-abc123", "0412"):
        assert leaked not in text
    assert "ValueError" in text  # failed rollback is logged too

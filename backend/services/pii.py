"""Shared stdlib-only contact-detail redaction for telemetry and reports."""
import re

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


"""`GET /api/search` `message` is plain JSON text (looper#37).

The message echoes the caller's `q`. Escaping it is the renderer's job: the
Jarvis dock uses escapeHtml(), the widget uses textContent, and the voice
output speaks it. The legacy map panel (localloop.pro-main index.html and
assets/js/main-map.js) puts it into innerHTML raw, and that fix belongs there
(MAP#324 + the main-map.js follow-up). These tests stop anyone "fixing" it
here by HTML-escaping, which would show `&amp;` in Jarvis and read it aloud.
"""
from models import Business

PAYLOAD = '<img src=x onerror=alert(1)>'


def _cafe(db):
    db.add(Business(name="Plain Text Cafe", category="café", suburb="Bondi",
                    lat=-33.8908, lng=151.2748, source="manual"))
    db.commit()


def test_message_with_results_echoes_markup_verbatim(client, db):
    # The map panel only renders `message` when results[] is non-empty,
    # so pin the echo on that path, not just the no-results path.
    _cafe(db)
    data = client.get("/api/search", params={"q": f"cafe {PAYLOAD}", "limit": "5"}).json()
    assert data["results"], "token 'cafe' must still match"
    assert PAYLOAD in data["message"]
    assert data["query"] == f"cafe {PAYLOAD}"


def test_message_without_results_echoes_markup_verbatim(client, db):
    data = client.get("/api/search", params={"q": PAYLOAD}).json()
    assert data["results"] == []
    assert PAYLOAD in data["message"]


def test_message_is_never_html_escaped(client, db):
    _cafe(db)
    q = "fish & chips cafe \"quoted\" 'x' <b>"
    data = client.get("/api/search", params={"q": q}).json()
    assert q in data["message"]
    for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&#x27;", "&#39;"):
        assert entity not in data["message"]


def test_response_is_json_not_html(client, db):
    r = client.get("/api/search", params={"q": PAYLOAD})
    assert r.headers["content-type"].startswith("application/json")

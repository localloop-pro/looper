"""looper#135: cap the search query length at the public boundary.

GET /api/search used to accept any q length, so one long multi-word query
built a very large OR'd LIKE expression. The Query boundary now enforces a
200-character maximum and returns 422 before the route runs.
"""

MAX_LENGTH = 200


def test_query_at_limit_is_accepted(client, db):
    resp = client.get("/api/search", params={"q": "a" * MAX_LENGTH})
    assert resp.status_code == 200


def test_query_one_over_limit_is_rejected_with_422(client, db):
    resp = client.get("/api/search", params={"q": "a" * (MAX_LENGTH + 1)})
    assert resp.status_code == 422


def test_query_over_limit_is_rejected_with_422(client, db):
    resp = client.get("/api/search", params={"q": "cafe " * 41})  # 205 chars
    assert resp.status_code == 422


def test_very_long_multi_word_query_is_rejected(client, db):
    # Close to the ~16 KB request-line budget the issue describes.
    q = " ".join(["hairdresser"] * 1200)
    resp = client.get("/api/search", params={"q": q})
    assert resp.status_code == 422

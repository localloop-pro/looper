"""GET /demo keeps the deep-link query string (looper#70).

/demo?cat=Food&q=coffee&fly=... must land on demo-map.html with the SAME
query, or the F4.2 deep link is silently lost. Only the query is carried:
the redirect target path is fixed, so input can never pick the host.
"""

DEMO_PAGE = "/web/jarvis/demo-map.html"


def test_demo_without_query_still_redirects(client):
    r = client.get("/demo", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == DEMO_PAGE


def test_demo_keeps_deep_link_query(client):
    qs = "cat=Food&q=coffee&fly=151.2743,-33.8908,16"
    r = client.get("/demo?" + qs, follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == DEMO_PAGE + "?" + qs


def test_demo_keeps_encoded_query_verbatim(client):
    qs = "q=caf%C3%A9%20near%20me&cat=Offers"
    r = client.get("/demo?" + qs, follow_redirects=False)
    assert r.headers["location"] == DEMO_PAGE + "?" + qs


def test_demo_redirect_is_never_off_site(client):
    # an absolute URL in the query stays a query VALUE on our own page
    for qs in ("next=https://evil.example", "//evil.example", "q=x&@evil.example"):
        r = client.get("/demo?" + qs, follow_redirects=False)
        loc = r.headers["location"]
        assert loc.startswith(DEMO_PAGE + "?"), loc

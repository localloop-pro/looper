"""GET /demo keeps the deep-link query, allowlisted (looper#70).

/demo?cat=Food&q=coffee&fly=... must land on demo-map.html with the same
deep link, or the F4.2 link is silently lost. Only cat, q and fly are
forwarded (first value of each, re-encoded by us); every other param,
including api=, is dropped. The target path is fixed, so the redirect is
always same-site.
"""
from urllib.parse import parse_qs, urlsplit

import pytest

DEMO_PAGE = "/web/jarvis/demo-map.html"


def _go(client, qs):
    r = client.get("/demo" + ("?" + qs if qs else ""), follow_redirects=False)
    assert r.status_code in (302, 307)
    return r.headers["location"]


def _params(loc):
    parts = urlsplit(loc)
    assert parts.scheme == "" and parts.netloc == "", loc
    assert parts.path == DEMO_PAGE, loc
    return parse_qs(parts.query)


def test_demo_without_query_still_redirects(client):
    assert _go(client, "") == DEMO_PAGE


def test_demo_keeps_deep_link_query(client):
    loc = _go(client, "cat=Food&q=coffee&fly=151.2743,-33.8908,16")
    assert loc == DEMO_PAGE + "?cat=Food&q=coffee&fly=151.2743,-33.8908,16"


def test_demo_drops_disallowed_params_keeps_allowed(client):
    loc = _go(client, "api=https://evil.example&cat=Food&next=//evil.example&q=coffee&utm_source=x")
    assert _params(loc) == {"cat": ["Food"], "q": ["coffee"]}
    assert "evil" not in loc and "api" not in loc


def test_demo_only_disallowed_params_gives_bare_page(client):
    assert _go(client, "api=http://127.0.0.1:9999&debug=1") == DEMO_PAGE


def test_demo_repeated_params_keep_first_value_only(client):
    loc = _go(client, "q=coffee&q=pizza&cat=Food&cat=Offers")
    assert _params(loc) == {"q": ["coffee"], "cat": ["Food"]}


def test_demo_encoded_values_round_trip(client):
    loc = _go(client, "q=caf%C3%A9%20near%20me&cat=Offers%26api%3Dx")
    # decoded value survives; the encoded & stays INSIDE cat, no new param
    assert _params(loc) == {"q": ["café near me"], "cat": ["Offers&api=x"]}


def test_demo_encoded_key_is_still_filtered(client):
    # %61pi decodes to "api" — still not allowlisted
    assert _go(client, "%61pi=https://evil.example") == DEMO_PAGE


def test_demo_header_injection_is_encoded(client):
    loc = _go(client, "q=a%0D%0ALocation:%20https://evil.example")
    assert "\r" not in loc and "\n" not in loc
    assert _params(loc) == {"q": ["a\r\nLocation: https://evil.example"]}


@pytest.mark.parametrize("qs", [
    "next=https://evil.example",
    "//evil.example",
    "q=x&@evil.example",
    "q=//evil.example",
    "fly=https://evil.example",
])
def test_demo_redirect_is_never_off_site(client, qs):
    loc = _go(client, qs)
    assert loc.startswith(DEMO_PAGE), loc
    _params(loc)  # relative, fixed path


@pytest.mark.parametrize("qs", [
    "q=&q=coffee",
    "cat=&cat=Food",
    "fly=&fly=151.2743,-33.8908,16",
    "q&q=coffee",
    "%71=&q=coffee",          # %71 is "q"
    "q=&%71=coffee",
    "%63at=&cat=Food",        # %63 is "c"
])
def test_demo_blank_first_value_is_not_replaced_by_later(client, qs):
    assert _go(client, qs) == DEMO_PAGE


def test_demo_blank_first_drops_only_that_key(client):
    loc = _go(client, "q=&cat=Food&q=coffee&fly=151.2743,-33.8908,16")
    assert _params(loc) == {"cat": ["Food"], "fly": ["151.2743,-33.8908,16"]}

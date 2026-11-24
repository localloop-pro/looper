"""Issue #193: lock the server-side maximums of limit and radius_km.

Each parameter is accepted at its maximum and rejected (422) one step above.
"""

import pytest

# (path, parameter, maximum)
BOUNDS = [
    ("/api/search", "limit", 20),
    ("/api/search", "radius_km", 5000),
    ("/api/discover", "limit", 50),
    ("/api/discover", "radius_km", 50),
    ("/api/businesses", "limit", 50),
    ("/api/pins", "limit", 500),
]


def _params(path, name, value):
    params = {name: value}
    if path == "/api/search":
        params["q"] = "cafe"
    return params


@pytest.mark.parametrize("path,name,maximum", BOUNDS)
def test_value_at_maximum_is_accepted(client, path, name, maximum):
    response = client.get(path, params=_params(path, name, maximum))
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("path,name,maximum", BOUNDS)
def test_value_above_maximum_is_rejected(client, path, name, maximum):
    response = client.get(path, params=_params(path, name, maximum + 1))
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("path,name,maximum", BOUNDS)
def test_zero_and_negative_values_are_rejected(client, path, name, maximum):
    for bad in (0, -1):
        response = client.get(path, params=_params(path, name, bad))
        assert response.status_code == 422, (bad, response.text)

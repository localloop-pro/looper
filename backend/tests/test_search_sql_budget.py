"""Issue #113: returned page size must not create per-row SQL reads."""
import pathlib
import sys

import models

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
from bench_search import SqlMeter, build_dataset  # noqa: E402


def _statement_count(client, meter, path, params):
    meter.reset()
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return meter.count


def test_search_sql_count_is_independent_of_limit(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "0")
    build_dataset(db, n_businesses=400, n_reviews=2000)
    meter = SqlMeter(models.engine)
    params = {
        "q": "cafe",
        "lat": -33.8908,
        "lng": 151.2743,
        "radius_km": 5,
    }

    one = _statement_count(client, meter, "/api/search", {**params, "limit": 1})
    twenty = _statement_count(client, meter, "/api/search", {**params, "limit": 20})

    assert one == twenty
    assert one <= 6


def test_discover_sql_count_is_independent_of_limit(client, db, monkeypatch):
    monkeypatch.setenv("LOOPER_READ_CACHE_TTL_S", "0")
    build_dataset(db, n_businesses=400, n_reviews=2000)
    meter = SqlMeter(models.engine)
    params = {"suburb": "Bondi"}

    one = _statement_count(client, meter, "/api/discover", {**params, "limit": 1})
    fifty = _statement_count(client, meter, "/api/discover", {**params, "limit": 50})

    assert one == fifty
    assert one <= 6

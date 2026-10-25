"""seed.py refuses production-shaped databases (looper#111)."""
import os

import pytest

from seed import refuse_reason

LOCAL = "sqlite:///data/looper.db"
PROD_ENV = ("LOOPER_ENV", "COOLIFY_URL", "SOURCE_COMMIT", "LOOPER_COMMIT", "LOOPER_ALLOW_SEED")


def test_local_file_allowed():
    assert refuse_reason(LOCAL, {}) is None


def test_app_path_refused():
    assert refuse_reason("sqlite:////app/data/looper.db", {})


def test_looper_env_production_refused():
    assert refuse_reason(LOCAL, {"LOOPER_ENV": "production"})


@pytest.mark.parametrize("key", ["COOLIFY_URL", "SOURCE_COMMIT", "LOOPER_COMMIT"])
def test_deploy_markers_refused(key):
    assert refuse_reason(LOCAL, {key: "abc"})
    if not key.startswith("COOLIFY_"):
        assert refuse_reason(LOCAL, {key: ""}) is None


def test_coolify_prefix_refused():
    assert refuse_reason(LOCAL, {"COOLIFY_FQDN": "x"})


def test_override_allows():
    env = {"LOOPER_ALLOW_SEED": "yes", "LOOPER_ENV": "production", "LOOPER_COMMIT": "abc"}
    assert refuse_reason("sqlite:////app/data/looper.db", env) is None
    assert refuse_reason(LOCAL, {"LOOPER_ALLOW_SEED": "true", "LOOPER_ENV": "production"})


@pytest.fixture()
def clean_env(monkeypatch):
    for key in PROD_ENV + tuple(k for k in os.environ if k.startswith("COOLIFY_")):
        monkeypatch.delenv(key, raising=False)


def test_main_refuses_and_writes_nothing(db, clean_env, monkeypatch):
    import seed
    from models import Business
    monkeypatch.setenv("LOOPER_ENV", "production")
    assert seed.main() == 2
    assert db.query(Business).count() == 0


def test_main_seeds_local(db, clean_env):
    import seed
    from models import Business
    assert seed.main() == 0
    assert db.query(Business).count() == 20

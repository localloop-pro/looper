"""Issue #86: /health reports the deployed commit from env, never from git."""
import subprocess

import pytest


@pytest.fixture
def no_commit_env(monkeypatch):
    monkeypatch.delenv("LOOPER_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    return monkeypatch


def test_health_truncates_commit_to_12_chars(client, no_commit_env):
    no_commit_env.setenv("LOOPER_COMMIT", "abc123def4567890")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy",
                               "organization_identity": "/api/identity/health",
                               "commit": "abc123def456"}


def test_health_commit_empty_when_unset_and_still_200(client, no_commit_env):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["commit"] == "" and body["status"] == "healthy"


def test_empty_build_arg_falls_back_to_coolify_runtime_source_commit(client, no_commit_env):
    # Built without the arg, the Dockerfile sets LOOPER_COMMIT="". Coolify still
    # injects SOURCE_COMMIT into the running container.
    no_commit_env.setenv("LOOPER_COMMIT", "")
    no_commit_env.setenv("SOURCE_COMMIT", "FEDCBA9876543210")
    assert client.get("/health").json()["commit"] == "fedcba987654"


@pytest.mark.parametrize("value", ["not-a-sha", "<script>", "abc 123", "HEAD"])
def test_non_hex_commit_is_not_echoed(client, no_commit_env, value):
    no_commit_env.setenv("LOOPER_COMMIT", value)
    response = client.get("/health")
    assert response.status_code == 200 and response.json()["commit"] == ""


def test_health_never_runs_git(client, no_commit_env):
    def forbidden(*_, **__):
        pytest.fail("/health must not run git at request time")
    no_commit_env.setattr(subprocess, "run", forbidden)
    no_commit_env.setattr(subprocess, "check_output", forbidden)
    no_commit_env.setattr(subprocess, "Popen", forbidden)
    assert client.get("/health").status_code == 200

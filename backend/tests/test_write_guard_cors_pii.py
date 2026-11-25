"""Unit tests for the small security helpers: write kill switch, CORS list, PII scrub."""
import pytest
from fastapi import HTTPException

from services import cors_policy, pii, write_guard


@pytest.mark.parametrize("value", [None, "", "True", "1", "yes", "TRUE", " true"])
def test_public_writes_off_unless_exactly_true(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("LOOPER_PUBLIC_WRITES", raising=False)
    else:
        monkeypatch.setenv("LOOPER_PUBLIC_WRITES", value)
    assert write_guard.public_writes_enabled() is False
    with pytest.raises(HTTPException) as exc:
        write_guard.require_public_writes()
    assert exc.value.status_code == 403


def test_public_writes_on_when_exactly_true(monkeypatch):
    monkeypatch.setenv("LOOPER_PUBLIC_WRITES", "true")
    assert write_guard.public_writes_enabled() is True
    assert write_guard.require_public_writes() is None


def test_dev_origins_parsing(monkeypatch):
    monkeypatch.setenv(
        "LOOPER_DEV_ORIGINS",
        " http://localhost:5173/ ,*, ,http://localhost:5173,http://localhost:3000",
    )
    assert cors_policy.dev_origins() == ["http://localhost:5173", "http://localhost:3000"]


def test_cors_options_never_wildcard_or_credentialed(monkeypatch):
    monkeypatch.setenv("LOOPER_DEV_ORIGINS", "*")
    opts = cors_policy.cors_options()
    assert opts["allow_credentials"] is False
    assert "*" not in opts["allow_origins"]
    assert opts["allow_origins"] == list(cors_policy.PRODUCTION_ORIGINS)
    assert all(o.startswith("https://") for o in opts["allow_origins"])


def test_cors_options_includes_dev_origins(monkeypatch):
    monkeypatch.setenv("LOOPER_DEV_ORIGINS", "http://localhost:3000")
    assert "http://localhost:3000" in cors_policy.cors_options()["allow_origins"]


def test_dev_origins_unset(monkeypatch):
    monkeypatch.delenv("LOOPER_DEV_ORIGINS", raising=False)
    assert cors_policy.dev_origins() == []


def test_scrub_pii_none_and_clean_text():
    assert pii.scrub_pii(None) is None
    assert pii.scrub_pii("cafes near Bondi") == "cafes near Bondi"


@pytest.mark.parametrize("raw", [
    "0412 345 678", "0412-345-678", "0412345678", "+61 412 345 678", "+61412345678",
])
def test_scrub_pii_au_mobiles(raw):
    assert pii.scrub_pii(f"call me on {raw} please") == "call me on [mobile] please"


def test_scrub_pii_email_and_mobile_together():
    out = pii.scrub_pii("a.b+c@mail.example.com or 0412 345 678")
    assert out == "[email] or [mobile]"

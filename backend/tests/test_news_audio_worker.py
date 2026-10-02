"""Unit coverage for the in-progress F6.1 news audio worker.

The real acceptance still requires an owner-approved Supabase bucket, TTS key,
scheduled task, and existing-player smoke test. These tests keep all local
content, idempotency, and failure paths deterministic without external calls.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from tools import news_audio_worker as worker


def test_strip_markup_and_build_tts_text(monkeypatch):
    monkeypatch.setattr(worker, "MAX_CHARS", 500)
    row = {
        "district_slug": "bondi-beach",
        "title": "Weekend update",
        "body": "## Hello **locals**. [Details](https://example.com) <b>now</b> https://bad.test",
        "created_at": "2026-08-12T00:00:00Z",
    }

    text = worker._build_tts_text(row)

    assert text.startswith("Local Loop Bondi Beach news, Wednesday 12 August 2026.")
    assert "Hello locals. Details now" in text
    assert "http" not in text
    assert "<b>" not in text


def test_tts_text_respects_character_cap(monkeypatch):
    monkeypatch.setattr(worker, "MAX_CHARS", 80)
    text = worker._build_tts_text({"title": "Title", "body": "x" * 500})
    assert len(text) == 80


class _SelectQuery:
    def __init__(self, responses):
        self._responses = responses

    def select(self, *_args, **_kwargs):
        return self

    def is_(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._responses.pop(0))


class _FakeSupabase:
    def __init__(self, responses):
        self._responses = responses

    def table(self, name):
        assert name == "news_post"
        return _SelectQuery(self._responses)


def _install_fake_supabase(monkeypatch, fake_client):
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda _url, _key: fake_client),
    )
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-only")
    monkeypatch.setattr(worker, "SUPABASE_URL", "https://example.invalid")
    monkeypatch.setattr(worker, "SUPABASE_SERVICE_KEY", "test-only")
    monkeypatch.setattr(worker, "TTS_PROVIDER", "openai")
    monkeypatch.setattr(worker, "TTS_API_KEY", "test-only")


def test_run_processes_once_then_skips_existing_audio(monkeypatch):
    fake = _FakeSupabase(
        [[{"id": "news-1", "title": "Update", "body": "Body", "payload": {}}], []]
    )
    _install_fake_supabase(monkeypatch, fake)
    generated: list[str] = []
    updates: list[tuple[str, str]] = []
    monkeypatch.setattr(worker, "_generate_audio", lambda text: generated.append(text) or b"mp3")
    monkeypatch.setattr(
        worker,
        "_upload_audio",
        lambda _sb, post_id, data: f"https://cdn.invalid/{post_id}-{len(data)}.mp3",
    )
    monkeypatch.setattr(
        worker,
        "_set_audio_url",
        lambda _sb, post_id, url: updates.append((post_id, url)),
    )

    worker.run()
    worker.run()

    assert len(generated) == 1
    assert updates == [("news-1", "https://cdn.invalid/news-1-3.mp3")]


def test_run_marks_failure_and_returns_nonzero(monkeypatch):
    fake = _FakeSupabase(
        [[{"id": "news-bad", "title": "Update", "body": "Body", "payload": {}}]]
    )
    _install_fake_supabase(monkeypatch, fake)
    marked: list[tuple[str, str]] = []
    monkeypatch.setattr(worker, "_generate_audio", lambda _text: (_ for _ in ()).throw(RuntimeError("tts down")))
    monkeypatch.setattr(
        worker,
        "_mark_error",
        lambda _sb, post_id, error: marked.append((post_id, error)),
    )

    with pytest.raises(SystemExit) as exc:
        worker.run()

    assert exc.value.code == 1
    assert marked == [("news-bad", "tts down")]

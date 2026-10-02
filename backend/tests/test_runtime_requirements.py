"""looper#55: backend/requirements.txt lists exactly what the API imports.

Every third-party import under backend/ (tests excluded) must be covered by
backend/requirements.txt, and packages nothing imports must not creep back.
"""
import ast
import pathlib
import re
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

# Local packages/modules, and optional deps installed from other files.
LOCAL = {"models", "schemas", "routes", "services", "main", "seed"}
OPTIONAL = {
    "sync": "brain/sync.py, path-inserted at call time",
    "typedb": "requirements-brain.txt (TYPEDB_ENABLED only)",
}
# import name -> requirement name
DIST = {"dotenv": "python-dotenv"}
REMOVED = {"openai", "aiosqlite", "geopy", "requests"}


def _requirements(path):
    names = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(re.split(r"[\[=<>!~ ]", line, 1)[0].lower())
    return names


def _runtime_imports():
    found = {}
    for f in BACKEND.rglob("*.py"):
        if {"tests", ".venv", "__pycache__"} & set(f.relative_to(BACKEND).parts):
            continue
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            else:
                continue
            for mod in mods:
                top = mod.split(".")[0]
                if top not in sys.stdlib_module_names:
                    found.setdefault(top, []).append(f"{f.relative_to(REPO)}:{node.lineno}")
    return found


def test_every_runtime_import_is_listed():
    reqs = _requirements(BACKEND / "requirements.txt")
    missing = {
        mod: where
        for mod, where in _runtime_imports().items()
        if mod not in LOCAL and mod not in OPTIONAL and DIST.get(mod, mod) not in reqs
    }
    assert not missing, f"imported but not in backend/requirements.txt: {missing}"


@pytest.mark.parametrize("pkg", sorted(REMOVED))
def test_unused_packages_stay_out(pkg):
    assert pkg not in _requirements(BACKEND / "requirements.txt")
    assert pkg not in _runtime_imports()


def test_tools_requirements_cover_news_worker():
    assert {"openai", "supabase"} <= _requirements(REPO / "tools" / "requirements.txt")


def test_facebook_pipeline_live_path_uses_httpx(db, monkeypatch):
    import httpx
    from services import facebook_pipeline

    calls = []

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"id": "p1", "message": "", "from": {"id": "u1"}}]}

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params["limit"], timeout))
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setitem(sys.modules, "requests", None)  # not installed
    assert facebook_pipeline.run_pipeline("tok", "grp", limit=3) == (0, 1)
    assert calls == [("https://graph.facebook.com/v19.0/grp/feed", 3, 30)]


def test_facebook_pipeline_demo_mode_needs_no_network(db, monkeypatch):
    import httpx
    from services import facebook_pipeline

    def boom(*a, **k):
        raise AssertionError("demo mode must not call the network")

    monkeypatch.setattr(httpx, "get", boom)
    imported, _ = facebook_pipeline.run_pipeline()
    assert imported > 0  # sample posts still import offline

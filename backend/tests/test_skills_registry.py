"""Skills registry checks (looper#71).

Every `.SEED/skills/<archetype>/<name>.md` must validate against
`.SEED/skills/schema.json`, sit in the folder named by its archetype, and
carry no PII. The loader lives in tools/skills_index.py so the test and the
Supa Admin index read entries the same way.
"""
import importlib.util
import json
import pathlib
import re

import pytest
from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("skills_index", ROOT / "tools" / "skills_index.py")
skills_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skills_index)

SCHEMA = skills_index.load_schema()
VALIDATOR = Draft202012Validator(SCHEMA)
ARCHETYPES = ["news", "events", "offers", "stays", "jobs", "dining", "media", "platform"]
ENTRIES = skills_index.entry_files()


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


def test_folders_are_exactly_the_archetypes():
    assert SCHEMA["properties"]["archetype"]["enum"] == ARCHETYPES
    assert [d.name for d in skills_index.archetype_dirs()] == sorted(ARCHETYPES)


def test_registry_has_entries():
    assert ENTRIES, "expected at least the worked example entry"


@pytest.mark.parametrize("path", ENTRIES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_entry_validates(path):
    _, problems = skills_index.check_entry(path, VALIDATOR)
    assert problems == []


# Members' contact details never go in the registry.
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")
_AU_MOBILE = re.compile(r"(?:\+?61[\s-]?|0)4(?:[\s-]?\d){8}")


@pytest.mark.parametrize("path", ENTRIES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_entry_has_no_contact_pii(path):
    text = path.read_text(encoding="utf-8")
    assert not _EMAIL.search(text)
    assert not _AU_MOBILE.search(text)


def test_index_generator_outputs_every_entry():
    index, problems = skills_index.build_index()
    assert problems == []
    json.dumps(index)  # serialisable for Supa Admin
    assert len(index["entries"]) == len(ENTRIES)
    example = next(e for e in index["entries"] if e["name"] == "ai-employees")
    assert example["file"] == ".SEED/skills/platform/ai-employees.md"
    assert example["status"] == "built"


# ── the checks reject what they should ──────────────────────────────────

GOOD = {
    "name": "demo",
    "form": "skill",
    "archetype": "news",
    "home_repo": "localloop.pro-main",
    "path": "assets/js/demo.js",
    "status": "candidate",
    "owner_floor": "localloop.pro-main",
    "risk": "low",
    "why": "A demo entry used only by this test.",
}


def _write(tmp_path, folder, stem, fields, extra=""):
    d = tmp_path / folder
    d.mkdir(exist_ok=True)
    body = "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + extra + "---\n\nbody\n"
    f = d / f"{stem}.md"
    f.write_text(body, encoding="utf-8")
    return f


def _problems(tmp_path, monkeypatch, folder="news", stem="demo", extra="", **changes):
    monkeypatch.setattr(skills_index, "ROOT", tmp_path)
    fields = {**GOOD, **changes}
    f = _write(tmp_path, folder, stem, {k: v for k, v in fields.items() if v is not None}, extra)
    return skills_index.check_entry(f, VALIDATOR)[1]


def test_good_entry_passes(tmp_path, monkeypatch):
    assert _problems(tmp_path, monkeypatch) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"form": "agent"},
        {"status": "done"},
        {"risk": "none"},
        {"home_repo": "some-other-repo"},
        {"archetype": "food"},
        {"path": "/abs/path.md"},
        {"path": "../outside.md"},
        {"why": "short"},
        {"name": "Demo"},
        {"risk": None},
    ],
    ids=str,
)
def test_bad_field_is_rejected(tmp_path, monkeypatch, changes):
    assert _problems(tmp_path, monkeypatch, **changes)


def test_unknown_key_is_rejected(tmp_path, monkeypatch):
    assert _problems(tmp_path, monkeypatch, extra="access: admin\n")


def test_duplicate_key_is_rejected(tmp_path, monkeypatch):
    assert _problems(tmp_path, monkeypatch, extra="risk: high\n")


def test_name_must_match_file(tmp_path, monkeypatch):
    assert _problems(tmp_path, monkeypatch, stem="other")


def test_archetype_must_match_folder(tmp_path, monkeypatch):
    assert _problems(tmp_path, monkeypatch, folder="events")


def test_looper_path_must_exist(tmp_path, monkeypatch):
    assert _problems(tmp_path, monkeypatch, home_repo="looper", path="nope/missing.py")


def test_frontmatter_must_open_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(skills_index, "ROOT", tmp_path)
    (tmp_path / "news").mkdir()
    f = tmp_path / "news" / "demo.md"
    f.write_text("# no frontmatter\n", encoding="utf-8")
    assert skills_index.check_entry(f, VALIDATOR)[1]


def test_quoted_values_are_unwrapped():
    data = skills_index.parse_frontmatter('---\nwhy: "a: quoted, value"\n---\n')
    assert data == {"why": "a: quoted, value"}

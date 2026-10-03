"""Citation format checks for skills registry entries (looper#89).

tools/check_skill_citations.py proves each `repo \`path:line\`` citation
resolves at its pinned commit, but needs local clones of the other repos, so
CI only checks the format here: every cited repo has a pinned commit.
"""
import importlib.util
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_skill_citations", ROOT / "tools" / "check_skill_citations.py"
)
cites = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cites)

ENTRIES = sorted(
    f for f in (ROOT / ".SEED" / "skills").glob("*/*.md") if f.name != "README.md"
)


def test_parse_reads_pins_and_citations():
    text = (
        "Pinned: looper @ `9becb9c` · map @ `13400a8`\n"
        "See looper `backend/routes/search.py:60` and map `a/b.mjs:7`, "
        "but not `unprefixed.py:3`.\n"
    )
    pins, found = cites.parse(text)
    assert pins == {"looper": "9becb9c", "map": "13400a8"}
    assert found == [("looper", "backend/routes/search.py", 60), ("map", "a/b.mjs", 7)]


@pytest.mark.parametrize("path", ENTRIES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_cited_repo_is_pinned(path):
    pins, found = cites.parse(path.read_text(encoding="utf-8"))
    assert {repo for repo, _, _ in found} <= set(pins)


def _head():
    out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return out.stdout.strip()


@pytest.mark.parametrize(
    "body, code",
    [
        ("looper `AGENTS.md:1`", 0),          # resolves
        ("looper `AGENTS.md:999999`", 1),     # past the end of the file
        ("looper `no/such/file.py:1`", 1),    # file not at that commit
        ("map `AGENTS.md:1`", 1),             # repo cited but not pinned
        ("cards `x.ts:1`\nPinned: cards @ `0000000`", 2),  # no clone has it
    ],
)
def test_check_exit_codes(tmp_path, body, code):
    entry = tmp_path / "e.md"
    entry.write_text(f"Pinned: looper @ `{_head()}`\n{body}\n", encoding="utf-8")
    assert cites.check([entry], {"looper": ROOT}) == code

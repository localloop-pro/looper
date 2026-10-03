#!/usr/bin/env python3
"""Check that every file:line citation in skills registry entries resolves (looper#89).

An entry pins the commits it read with a line like

    Pinned: looper @ `9becb9c` · map @ `13400a8` · cards @ `7a0e584`

and cites code as  looper `backend/routes/search.py:60`  (repo word, then the
path:line in backticks). This script runs `git show <commit>:<path>` in each
repo's local clone and checks the cited line exists and is not blank.
Read-only: it never fetches, checks out or writes anything.

    python3 tools/check_skill_citations.py \
        --repo map=../localloop.pro-main --repo cards=../hybridcard-v2

`looper` defaults to this repo. Prints every citation with the cited line.
Exit 0 = all resolve, 1 = at least one does not, 2 = a cited repo or pinned
commit is not available locally (nothing could be proved for it).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".SEED" / "skills"

REPOS = ("looper", "map", "cards")
_PIN = re.compile(r"\b(looper|map|cards) @ `([0-9a-f]{7,40})`")
_CITE = re.compile(r"\b(looper|map|cards) `([^`\s:]+):(\d+)`")


def parse(text: str) -> tuple[dict[str, str], list[tuple[str, str, int]]]:
    """Return ({repo: pinned commit}, [(repo, path, line), ...]) from one entry."""
    pins = {repo: commit for repo, commit in _PIN.findall(text)}
    cites = [(repo, path, int(line)) for repo, path, line in _CITE.findall(text)]
    return pins, cites


def cited_line(clone: pathlib.Path, commit: str, path: str, line: int) -> str | None:
    """The text of `line` in `path` at `commit`, or None if it does not exist."""
    out = subprocess.run(
        ["git", "-C", str(clone), "show", f"{commit}:{path}"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return None
    lines = out.stdout.splitlines()
    return lines[line - 1] if 1 <= line <= len(lines) else None


def check(files, clones: dict[str, pathlib.Path]) -> int:
    bad = missing = total = 0
    for f in files:
        rel = f.relative_to(ROOT).as_posix() if f.is_relative_to(ROOT) else str(f)
        pins, cites = parse(f.read_text(encoding="utf-8"))
        print(f"== {rel} ({len(cites)} citations)")
        for repo, path, line in cites:
            total += 1
            commit, clone = pins.get(repo), clones.get(repo)
            if not commit:
                print(f"  BAD   {repo} {path}:{line}  no 'Pinned: {repo} @ `<commit>`' line")
                bad += 1
                continue
            if clone is None or subprocess.run(
                ["git", "-C", str(clone), "cat-file", "-e", f"{commit}^{{commit}}"],
                capture_output=True,
            ).returncode != 0:
                print(f"  SKIP  {repo} {path}:{line}  no clone with {commit} (pass --repo {repo}=<path>)")
                missing += 1
                continue
            text = cited_line(clone, commit, path, line)
            if text is None or not text.strip():
                print(f"  BAD   {repo}@{commit} {path}:{line}  line missing or blank")
                bad += 1
            else:
                print(f"  ok    {repo}@{commit} {path}:{line}  {text.strip()[:90]}")
    print(f"{total} citations: {total - bad - missing} ok, {bad} bad, {missing} skipped")
    return 1 if bad else 2 if missing else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", action="append", default=[], metavar="NAME=PATH",
                    help="local clone for map or cards (looper defaults to this repo)")
    ap.add_argument("files", nargs="*", type=pathlib.Path,
                    help="entry files (default: every .SEED/skills/<archetype>/*.md)")
    args = ap.parse_args(argv)

    clones = {"looper": ROOT}
    for spec in args.repo:
        name, _, path = spec.partition("=")
        if name not in REPOS or not path:
            ap.error(f"--repo wants one of {', '.join(REPOS)}=<path>, got {spec!r}")
        clones[name] = pathlib.Path(path).expanduser().resolve()
    files = [f.resolve() for f in args.files] or sorted(
        f for f in SKILLS.glob("*/*.md") if f.name != "README.md"
    )
    return check(files, clones)


if __name__ == "__main__":
    sys.exit(main())

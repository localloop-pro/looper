#!/usr/bin/env python3
"""Skills registry index (looper#71).

Reads every `.SEED/skills/<archetype>/<name>.md`, checks its frontmatter
against `.SEED/skills/schema.json` and prints one JSON index to stdout, so
Supa Admin (or anything else) can read the registry without parsing Markdown.

    pip install -r backend/requirements-dev.txt   # jsonschema
    python3 tools/skills_index.py > /tmp/skills-index.json

Exit 0 = every entry valid, 1 = at least one problem (listed on stderr).
The index is generated on demand and never committed: a shared list would
conflict on every parallel PR (looper#53).

Frontmatter is a strict subset of YAML: one `key: value` per line, values
optionally wrapped in double quotes, no nesting, no comments. That keeps it
readable by a ten-line parser in any language.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".SEED" / "skills"
SCHEMA = SKILLS / "schema.json"

_LINE = re.compile(r"^([a-z_]+): (.+)$")


class FrontmatterError(ValueError):
    pass


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return the flat key/value frontmatter at the top of an entry."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise FrontmatterError("file must start with a '---' line")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise FrontmatterError("no closing '---' line") from None
    data: dict[str, str] = {}
    for n, line in enumerate(lines[1:end], start=2):
        m = _LINE.match(line)
        if not m:
            raise FrontmatterError(f"line {n}: expected 'key: value', got {line!r}")
        key, value = m.group(1), m.group(2).strip()
        if key in data:
            raise FrontmatterError(f"line {n}: duplicate key {key!r}")
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        data[key] = value
    return data


def archetype_dirs() -> list[pathlib.Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def entry_files() -> list[pathlib.Path]:
    """Every entry: .md files one level down. Folder READMEs are not entries."""
    return sorted(
        f
        for d in archetype_dirs()
        for f in d.glob("*.md")
        if f.name != "README.md"
    )


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def check_entry(path: pathlib.Path, validator) -> tuple[dict | None, list[str]]:
    """Validate one entry file. Returns (frontmatter or None, problems)."""
    rel = path.relative_to(ROOT).as_posix()
    try:
        data = parse_frontmatter(path.read_text(encoding="utf-8"))
    except FrontmatterError as e:
        return None, [f"{rel}: {e}"]
    problems = [
        f"{rel}: {'/'.join(map(str, err.path)) or '(entry)'}: {err.message}"
        for err in sorted(validator.iter_errors(data), key=str)
    ]
    if data.get("name") != path.stem:
        problems.append(f"{rel}: name {data.get('name')!r} must equal the file name {path.stem!r}")
    if data.get("archetype") != path.parent.name:
        problems.append(
            f"{rel}: archetype {data.get('archetype')!r} must equal its folder {path.parent.name!r}"
        )
    if data.get("home_repo") == "looper" and data.get("path"):
        if not (ROOT / data["path"]).exists():
            problems.append(f"{rel}: path {data['path']!r} does not exist in looper")
    return data, problems


def build_index() -> tuple[dict, list[str]]:
    from jsonschema import Draft202012Validator

    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    allowed = schema["properties"]["archetype"]["enum"]

    problems = [
        f".SEED/skills/{d.name}/: folder is not an archetype in schema.json"
        for d in archetype_dirs()
        if d.name not in allowed
    ]
    entries = []
    for f in entry_files():
        data, errs = check_entry(f, validator)
        problems += errs
        if data is not None and not errs:
            entries.append({**data, "file": f.relative_to(ROOT).as_posix()})
    index = {"version": 1, "archetypes": allowed, "entries": entries}
    return index, problems


def main() -> int:
    index, problems = build_index()
    for p in problems:
        print(p, file=sys.stderr)
    json.dump(index, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

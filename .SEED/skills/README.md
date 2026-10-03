# .SEED/skills/ — shared skills registry (looper#71)

One list of the skills, plugins, MCP tools and reusable functions across
LocalLoop's three repos (looper, localloop.pro-main, hybridcard-v2), grouped
by archetype. It lives in looper; Supa Admin will read it later.

**The registry is documentation and routing, not access.** An entry grants
no permission and installs nothing. It records what exists or should exist,
which repo owns it, and who shares it.

Open owner questions on this layout: [GRILL-ME.md](GRILL-ME.md).

## Folders

Six map archetypes, named by the label the map shows
(localloop.pro-main `assets/js/category-taxonomy.js`), plus two
registry-only folders:

| Folder      | Map key (taxonomy) | Also called                                |
|-------------|--------------------|--------------------------------------------|
| `news/`     | `News`             | gateway subagent `news`                    |
| `events/`   | `Events`           | HybridCard archetype `events`              |
| `offers/`   | `Offers`           | gateway subagent `offers`                  |
| `stays/`    | `Accommodation`    | HybridCard `accommodation`, gateway `stays`|
| `jobs/`     | `Job-Offers`       | gateway subagent `jobs`                    |
| `dining/`   | `Food`             | HybridCard `food`, gateway `food`, map agent `food-agent` |
| `media/`    | —                  | MCP servers, plugins, media tools (audio, image, video) |
| `platform/` | —                  | cross-cutting: auth, bridge, deploy, QA, AI team |

Rules:

- No other folders without the owner's OK on an issue. The test fails on an
  unknown folder.
- Pick the archetype the **end user** sees. If the behaviour serves every
  archetype, it goes in `platform/`.
- Empty folders keep a `.gitkeep`. Folder `README.md` files are allowed and
  are not entries.

## Entry format

One file per entry: `.SEED/skills/<archetype>/<name>.md`. Never a shared list
(looper#53): each PR adds or edits its own file, so parallel PRs don't
conflict.

```markdown
---
name: ai-employees
form: skill
archetype: platform
home_repo: hybridcard-v2
path: .claude/skills/ai-employees/SKILL.md
status: built
owner_floor: hybridcard-v2
risk: medium
why: One line on what repeats or is done by hand that this captures.
---

# Free Markdown body: evidence with file:line, mirrors, who shares it,
# why this risk level.
```

| Field         | Values | Notes |
|---------------|--------|-------|
| `name`        | kebab-case | must equal the file name |
| `form`        | `function` · `skill` · `plugin` · `mcp` | function = code you call; skill = SKILL.md for coding agents; plugin = bundle; mcp = MCP server or tool |
| `archetype`   | one of the 8 folders | must equal the folder |
| `home_repo`   | `looper` · `localloop.pro-main` · `hybridcard-v2` | the one repo that owns it |
| `path`        | repo-relative | for `looper`, the test checks it exists |
| `status`      | `candidate` → `approved` → `built` → `shared` | `approved` needs the owner's OK on an issue |
| `owner_floor` | kebab-case | until GRILL-ME Q6 is answered, the home repo name |
| `risk`        | `low` · `medium` · `high` | see below |
| `why`         | one line, 10–200 chars | |

Frontmatter is strict: one `key: value` per line, values may be wrapped in
double quotes, no nesting, no comments, no extra keys. The full rules are in
[`schema.json`](schema.json) (JSON Schema 2020-12).

### Risk

- `high`: writes data, sends SMS/email/messages, spends money, calls an LLM
  on a platform key, or touches a hot zone (payments, SMS, auth/identity,
  VIP/tokens, BRIDGE-CONTRACT-v1). Never past `candidate` without auth, rate
  limits and the owner's OK on the issue.
- `medium`: reads private data, or teaches/changes code that does a `high`
  thing behind an existing approval gate.
- `low`: read-only on public data, or docs only.

Nothing in the registry may reorder search results (`rank_boost` is always
`false`). No PII in entries: no names of members, phone numbers, emails or
VIP identities.

## Check and index

```bash
# from the repo root
cd backend && .venv/bin/python -m pytest -q tests/test_skills_registry.py && cd ..
# machine-readable index for Supa Admin (stdout, never committed)
backend/.venv/bin/python tools/skills_index.py > /tmp/skills-index.json
```

`tools/skills_index.py` exits 1 and lists every problem on stderr if an entry
is invalid. CI runs the test with the rest of the backend suite.

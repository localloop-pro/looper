# #79 — Skills registry layout: owner answers (opened 2026-10-03)

**Status: DECIDED 2026-10-04. Bill answered all seven questions on looper#79.**

**Owner evidence:** https://github.com/localloop-pro/looper/issues/79#issuecomment-5978692365

Bill's comment, verbatim (posted 2026-10-04T09:52:07Z from the owner account
`localloop-pro`, author association OWNER; the handoff of 2026-10-05 names
this exact comment as his answer): "all proposals OK; D platform; F repo
names; G index in Supa-admin/."

The skills registry (looper#71) folders, schema and `GRILL-ME.md` reached
`main` through PR #105 (stacked on PR #80). The reasoning and `file:line`
evidence are in `.SEED/skills/GRILL-ME.md`. Only a comment from the owner on
looper#79 may fill the "Owner answer" column.
`backend/tests/test_skills_answers_record.py` checks the record: DECIDED
needs all seven answers and the numeric owner-comment link above, and the
table has exactly one row for each of A–G.

| Q | Question | Proposal | Owner answer |
|---|----------|----------|--------------|
| A | `media`: registry-only folder or also a 7th map archetype? Whole MCP server → `media/`; single-archetype MCP tool (e.g. HC `get_menu`) → that archetype's folder? | Registry only; yes to that split; cross-archetype tools → `platform/` | Proposal OK: `media/` is registry only, not a map archetype. Whole MCP server → `media/`; single-archetype MCP tool → that archetype; cross-archetype → `platform/` |
| B | Folder names: map labels (`stays`, `jobs`, `dining`) or code ids (`accommodation`, `job-offers`, `food`)? | Map labels, alias table in `.SEED/skills/README.md` | Proposal OK: map labels (`stays`, `jobs`, `dining`), alias table in the README |
| C | HybridCard-only archetypes (`retail, health, trades, professional, creative, driver`) | File under the map archetype the end user sees (retail deals → `offers`), else `platform/` | Proposal OK: the map archetype the end user sees, else `platform/`; no new folders |
| D | `fetch` (Fetch_Deliveries, outside the map taxonomy) | Own folder, `platform/`, or wait for the map. No proposal yet. | `platform/` |
| E | Home repo for a skill shared by 2+ repos | The repo where its code runs | Proposal OK: the repo where its code runs |
| F | `owner_floor` names | Repo names (today's default) or numbered floors ("floor 1" = Supa Admin) | Repo names (`looper`, `localloop.pro-main`, `hybridcard-v2`) |
| G | Who moves `candidate → approved`, and where is the JSON index published for Supa Admin? | Owner's comment on the entry's "Skill: …" issue; publish location open | Proposal OK: the owner's comment on the entry's "Skill: …" issue. Index published in `Supa-admin/` |

## What this decides

- Folders stay exactly as on `main`: six map labels plus `media/` and
  `platform/`. No `fetch/` folder: Fetch_Deliveries skills go in `platform/`.
- `owner_floor` = the home repo name; no numbered floors.
- `candidate → approved` needs Bill's comment on that entry's "Skill: …"
  issue. A registry entry still grants no access, installs nothing and never
  changes search order.
- The JSON index from `tools/skills_index.py` is published in `Supa-admin/`
  (outside this repo). Looper only generates it; nothing here deploys or
  pushes it, and it is never committed in looper.
- Done in the PR that closes looper#79 (#106): this record,
  `.SEED/skills/README.md`, `schema.json` and `GRILL-ME.md` §3.

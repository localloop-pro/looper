# #79 — Skills registry layout: owner answers (opened 2026-10-03)

**Status: AWAITING OWNER. Nothing below is decided yet.**

**Owner evidence:** _pending_

The skills registry (looper#71) needs seven answers from Bill before its
folders are locked. Its folders, schema and `GRILL-ME.md` reached `main`
through PR #105 (stacked on PR #80). The reasoning and the `file:line`
evidence are in `.SEED/skills/GRILL-ME.md` §3. No agent may fill in the
"Owner answer" column. Only a comment from the owner on looper#79 counts.
`backend/tests/test_skills_answers_record.py` checks that: while Status is
AWAITING OWNER every answer and the owner evidence must stay `_pending_`,
and the table has exactly one row for each of A–G.

| Q | Question | Proposal | Owner answer |
|---|----------|----------|--------------|
| A | `media`: registry-only folder or also a 7th map archetype? Whole MCP server → `media/`; single-archetype MCP tool (e.g. HC `get_menu`) → that archetype's folder? | Registry only; yes to that split; cross-archetype tools → `platform/` | _pending_ |
| B | Folder names: map labels (`stays`, `jobs`, `dining`) or code ids (`accommodation`, `job-offers`, `food`)? | Map labels, alias table in `.SEED/skills/README.md` | _pending_ |
| C | HybridCard-only archetypes (`retail, health, trades, professional, creative, driver`) | File under the map archetype the end user sees (retail deals → `offers`), else `platform/` | _pending_ |
| D | `fetch` (Fetch_Deliveries, outside the map taxonomy) | Own folder, `platform/`, or wait for the map. No proposal yet. | _pending_ |
| E | Home repo for a skill shared by 2+ repos | The repo where its code runs | _pending_ |
| F | `owner_floor` names | Repo names (today's default) or numbered floors ("floor 1" = Supa Admin) | _pending_ |
| G | Who moves `candidate → approved`, and where is the JSON index published for Supa Admin? | Owner's comment on the entry's "Skill: …" issue; publish location open | _pending_ |

## Until the owner answers

- The layout on `main` stays a proposal. New entries keep
  `status: candidate` and `owner_floor` = home repo name.
- No registry entry grants access, installs anything or changes search order.
  That holds whatever the answers are.

## When the owner answers

looper#79 stays open until then. Record the answers in a follow-up PR that
closes it:

1. Copy each answer into the table ("all proposals OK" fills A, B, C, E, G
   with the proposal; D, F and G's publish location still need a choice).
2. Change **Status** to `DECIDED <date>`. In the owner-evidence line at the
   top, replace `_pending_` with the full link to the owner's answering
   comment:
   `https://github.com/localloop-pro/looper/issues/79#issuecomment-<number>`.
   First check that the comment really is Bill's answer, not a team reminder
   (agents post from the same account). The test fails if a row is still
   `_pending_`, a row is missing, duplicated or extra (indented or not), or
   the link is not a numeric comment on looper#79. Keep the answers in the
   one table; no other line in this file may contain a pipe
   character.
3. Update `.SEED/skills/README.md`, its folders and `GRILL-ME.md` §3 to
   match, in that same follow-up PR.

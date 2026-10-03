# #79 — Skills registry layout: owner answers (opened 2026-10-03)

**Status: AWAITING OWNER. Nothing below is decided yet.**

The skills registry (looper#71, PR #80) needs seven answers from Bill
before its folders are locked. The reasoning and the `file:line` evidence
are in `.SEED/skills/GRILL-ME.md` (on branch `swarm/issue-71-ken` until
PR #80 merges). No agent may fill in the "Owner answer" column. Only a
comment from the owner on looper#79 counts.

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

- PR #80's layout stays a proposal. New entries keep `status: candidate`.
- No registry entry grants access, installs anything or changes search order.
  That holds whatever the answers are.

## When the owner answers

1. Copy each answer into the table ("all proposals OK" fills A, B, C, E, G
   with the proposal; D, F and G's publish location still need a choice).
2. Change **Status** to `DECIDED <date>` and link the owner's comment.
3. Update `.SEED/skills/README.md`, its folders and `GRILL-ME.md` §3 to
   match, in the same PR.

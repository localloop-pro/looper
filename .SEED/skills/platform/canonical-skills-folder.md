---
name: canonical-skills-folder
form: skill
archetype: platform
home_repo: hybridcard-v2
path: .claude/skills
status: candidate
owner_floor: hybridcard-v2
risk: low
why: HybridCard keeps byte-identical skill copies in .claude and .agents plus Cursor-only skills, so agents see different skills and copies drift silently.
---

# canonical-skills-folder (inventory top-5 #1)

One canonical skills folder in hybridcard-v2, with every other agent folder a
generated mirror and a CI `diff -r` check that fails on drift. Inventory rows
B1 and B2 (`docs/skills/INVENTORY.md`, looper#72).

Pinned: looper @ `9becb9c` · map @ `13400a8` · cards @ `7a0e584`

## Evidence

- Two byte-identical copies of the same skills (`diff -r` empty):
  cards `.claude/skills/ai-employees/SKILL.md:2` = cards `.agents/skills/ai-employees/SKILL.md:2`;
  cards `.claude/skills/typedb/SKILL.md:2` = cards `.agents/skills/typedb/SKILL.md:2`.
- A skill only one agent folder has: cards `.agents/skills/typesafe-ai/SKILL.md:2`
  (Claude Code agents never see it).
- A TypeQL reference at the wrong path, so Cursor can't load it as a named
  skill: cards `.cursor/skills/SKILLS.md:2` (`name: typeql`, overlaps `typedb`).
- A Cursor-only skill with a prompt copy: cards `.cursor/skills/branding-web-sentiment/SKILL.md:2`
  and cards `.prompts/branding-kit/web-sentiment-research.md:3`.

## Proposed scope

1. Pick the canonical folder (owner call: `.claude/skills` or `.agents/skills`;
   `path` above is a placeholder until then). Mirror the other with a script,
   not symlinks (they break on some Windows checkouts).
2. Add `typesafe-ai` to the canonical side.
3. Move the typeql text to `typedb/references/typeql.md` and link it from
   `typedb/SKILL.md`; delete the loose `.cursor/skills/SKILLS.md`.
4. CI step: `diff -r` canonical vs mirror, fail on any difference.

Out of scope: moving `branding-web-sentiment` (row B3). The move itself is
harmless, but that skill's Phase 4 populates the Branding Kit
(cards `.cursor/skills/branding-web-sentiment/SKILL.md:100`), so it is HIGH and
gets its own entry and owner OK.

## Shared with

- hybridcard-v2 (home): its Claude Code, Codex and Cursor agents.
- looper: agents working on `brain/` read `typedb` (looper `brain/sync.py:259`
  writes TypeDB).
- localloop.pro-main: none today.

## Why risk `low`

Matches inventory rows B1 and B2 (low): moves and mirrors Markdown, adds a
CI diff. No runtime code, data, messages, money or LLM calls change.

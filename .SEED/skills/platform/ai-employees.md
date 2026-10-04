---
name: ai-employees
form: skill
archetype: platform
home_repo: hybridcard-v2
path: .claude/skills/ai-employees/SKILL.md
status: built
owner_floor: hybridcard-v2
risk: medium
why: Agents building or debugging HybridCard's seven AI employees kept re-learning the gate, runner, inbox and BYOK metering by hand.
---

# ai-employees (worked example)

Coding-agent skill for HybridCard's AI team (Scout, Leo, Maya, Pete, Sage,
Nova, Finn): the Draft/Triggered/Autonomous gate, employee runs, the
scheduler tick, the Research Inbox and the owner MCP tools.

Checked against hybridcard-v2 @ `7a0e584`.

## Where it lives

- Canonical: `hybridcard-v2/.claude/skills/ai-employees/SKILL.md` (175 lines)
  with `references/` (autonomy-gate, runner-spine, research-inbox,
  metering-and-models, mcp-owner-tools, testing, employees/) and
  `evals/evals.json`.
- Mirror: `hybridcard-v2/.agents/skills/ai-employees/` is byte-identical
  today (`diff -rq` prints nothing). Two copies drift; deduping is a
  follow-up for the hybridcard-v2 floor, not a change here.
- Code it describes: `hybridcard-v2/src/lib/aiEmployees/` (`gate.ts`,
  `runner.ts`, `schedule.ts`, `research.ts`, `employees/*.ts`).

## Why `platform`

Employees work for any card archetype (food, accommodation, retail, …), so
the skill is cross-cutting, not tied to one map archetype.

## Why risk `medium`

The skill itself is documentation. The behaviour it teaches runs LLM calls
metered on the owner's BYOK key and reads a Stripe snapshot (Finn), so a
wrong change there costs money; everything ships as drafts behind the
owner-approval gate. Payments and the gate stay with the hybridcard-v2
owners (hot zone).

## Shared with

Nobody yet. Looper and localloop.pro-main do not run AI employees. Status
moves to `shared` only if another repo starts using it.

# #69 — One operational status file (2026-10-03)

`STATUS.md` at the repository root is the single current status file, at most
30 lines, updated weekly every Monday and when a material gate changes.
`plans/IMPLEMENTATION_PLAN.md` and feature checklists define scope and
acceptance; unchecked boxes alone do not prove code is absent or deployed.

`plans/BOT_HANDOFF.md` and `plans/COMPLETION_STATUS.md` have moved to
`plans/archive/` as historical evidence, with a superseded notice. Historical
audit references now point readers at the current status instead.

Cite an issue, merged PR, file or test for each claim. Distinguish merged code,
dark flags, owner deployment and end-to-end acceptance. Production facts that
cannot be verified from repository evidence say “unverified (owner probe
needed)”; agents do not probe production for status updates.

Assumption: #69 is the active approved docs-only task. This repo has no
`featured_webapp_SPEC.TXT`, `Featured_todo.md` or `Featured_done.db`; do not
invent parallel trackers. The issue/PR and STATUS.md track this cycle.

Verify from the repo root (no production access):
```bash
wc -l STATUS.md
rg -n --hidden 'BOT_HANDOFF|COMPLETION_STATUS' --glob '*.md' --glob '!node_modules/**' --glob '!looper-bot/node_modules/**' --glob '!backend/.venv/**' .
git diff --check
```
Expected: at most 30 lines; references only in `plans/archive/` and this
file; no whitespace errors. Rollback: revert the #69 docs commit through a
reviewed PR; no service, configuration or data changes are needed.

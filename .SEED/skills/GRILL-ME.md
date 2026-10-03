# GRILL-ME — skills registry layout (looper#71)

Before the folders are locked, this file states the proposed layout, attacks
it with the questions the code can answer, and lists what only the owner can
answer. The owner's answers (looper#79) go in
`.SEED/decisions/79-skills-registry-answers.md`; then this file is updated
to point at them.

Sources read (read-only), pinned:

- **MAP** = localloop.pro-main @ `13400a8`
- **HC** = hybridcard-v2 @ `7a0e584`
- **LOOPER** = this repo, branch for looper#71

## 1. Proposed layout

```
.SEED/skills/
├── README.md        what the registry is, folder rules, entry format
├── GRILL-ME.md      this file
├── schema.json      JSON Schema 2020-12 for one entry's frontmatter
├── news/  events/  offers/  stays/  jobs/  dining/   ← map archetypes
├── media/           MCP servers, plugins, media tools (registry-only)
└── platform/        cross-cutting: auth, bridge, deploy, QA, AI team
    └── ai-employees.md   worked example (status: built)
```

- One file per entry, `<archetype>/<name>.md`; flat frontmatter
  `name, form, archetype, home_repo, path, status, owner_floor, risk, why`.
- `tools/skills_index.py` prints a JSON index on demand (never committed,
  looper#53). `backend/tests/test_skills_registry.py` validates every entry.
- Folder names are the **labels the map shows** (Stays, Jobs, Dining), not
  the internal keys (Accommodation, Job-Offers, Food).

## 2. Self stress-test (answered from the code)

**Q1. Where do the six archetypes come from, and are they stable?**
MAP `assets/js/category-taxonomy.js:14-47` is the declared "single source of
truth for archetype → sub-category" (`:2`). Keys: `News :15`, `Events :20`,
`Offers :25`, `Accommodation :30`, `Job-Offers :37`, `Food :42`; labels at
`:16, :21, :26, :31, :38, :43`. MAP `assets/js/agent-registry.js:4-7` derives
one agent per archetype from that taxonomy "so the rail, voice bridge, and
gateway-facing labels cannot silently drift apart". → Six is right for the map.

**Q2. Why folder `dining`, when everything else in code says `food`?**
It doesn't match code ids: MAP `agent-registry.js:39` id `food-agent`;
MAP `workers/looper-gateway/src/index.mjs:57` subagent id `food` and `:72`
`food-agent` / archetype `Food`; HC `src/types/archetypes.ts:5` `'food'`.
Only the taxonomy label (`category-taxonomy.js:43`) says Dining. Same split
for `stays` (key `Accommodation`, HC `'accommodation'` `archetypes.ts:6`) and
`jobs` (key `Job-Offers`). → Kept the issue's label-based names (they are what
people see and what Supa Admin will show) and put the alias table in
README.md. **Owner to confirm (Q-B).**

**Q3. Do HybridCard card archetypes map 1:1 onto the six?**
No. HC `src/types/archetypes.ts:4-14` has ten: `food, accommodation, retail,
health, trades, professional, events, creative, driver, other`. The bridge
mapping HC `src/lib/bridge/payload.ts:19-30` sends them to Looper as
categories (`food → café`, `accommodation`, `events → event`, `retail → shop`,
…; `other` and `driver` "never fed"). So:
- HC has no `news`, `offers` or `jobs` archetype;
- `retail, health, trades, professional, creative, driver` have no map
  archetype.
→ The registry cannot be keyed by HC archetype. **Owner to decide where
HC-only archetype skills go (Q-C).**

**Q4. Can the registry join on Looper's brain `archetype_id`?**
No. LOOPER `brain/sync.py:148` stores `archetype_id or category or "other"`,
and the bridge sends the **raw HC archetype** (HC `payload.ts:45-46`), so
TypeDB holds HC vocabulary (`food`), not map vocabulary (`Food`/`dining`).
`brain/schema/002_business.tql:17` types it as a free string. → Registry
`archetype` is its own field; never join it to `archetype_id` without the
alias table.

**Q5. Is there an archetype the map uses that the taxonomy does not list?**
Yes: MAP `workers/looper-gateway/src/index.mjs:64-65` adds `fetch-agent`
(archetype `Fetch_Deliveries`, `:73`) "intentionally outside the taxonomy",
and the general router `SUBAGENTS` (`:50-60`) also has `fetch`, `claims`,
`geo_intelligence`, `notifications`. → Under this layout `claims`,
`geo_intelligence`, `notifications` are cross-cutting → `platform/`.
`fetch` has no clear home. **Owner to decide (Q-D).**

**Q6. Where are MCP surfaces today, and do they all belong in `media/`?**
- HC per-card MCP: `src/app/mcp/[slug]/manifest/route.ts`,
  `src/app/mcp/[slug]/tool/[name]/route.ts`, `src/app/api/mcp/[cardId]/route.ts`;
  tool list `src/lib/mcp/toolRegistry.ts:15`; per-archetype `mcpTools`
  (`archetypes.ts:42`, e.g. food `:114`: `get_menu`, `get_deals`, …).
- MAP looper-gateway `/mcp`: `workers/looper-gateway/src/index.mjs:210-216`,
  tools `looper_chat :85`, `map_search_proposal :100`,
  `pins_propose_create :115`, `business_report_stale :132`,
  `actions_confirm :154`.
- LOOPER looper-bot tools: `looper-bot/electron/tool-policy.cjs:12-21`
  (need a human click) and `:24-48` (run without one).
→ Proposal: the **server** (a whole MCP surface) is one entry in `media/`;
a **tool** that serves one archetype (e.g. HC `get_menu`) is an entry with
`form: mcp` in that archetype's folder; cross-archetype tools go to
`platform/`. **Owner to confirm (Q-A).**

**Q7. Are skills duplicated across agent folders?**
Yes. HC `.claude/skills/ai-employees/` and `.agents/skills/ai-employees/` are
byte-identical (`diff -rq` empty), same for `typedb/`. HC
`.cursor/skills/SKILLS.md` is a `typeql` skill (`name: typeql`, line 2) that
overlaps `typedb`. → One registry entry per behaviour, `path` = canonical
copy, mirrors listed in the body (see `platform/ai-employees.md`). Dedup
work belongs to the HC floor ("Skill: …" issue there, via looper#72's
inventory).

**Q8. Should the registry be one JSON/YAML list?**
No: every parallel PR would conflict on its end (looper#53,
`.SEED/decisions/53-one-file-per-entry.md`). One file per entry; the index is
generated (`tools/skills_index.py`).

**Q9. Can an entry grant or imply access?**
It must not. MAP `agent-registry.js:7` already sets the precedent ("routing
hints only; it does not grant an agent write access"). The schema has
`additionalProperties: false`, so no `access`/`token`/`key` field can be
added without a schema change in review. Risk `high` = writes, messages,
money, platform-key LLM calls or a hot zone; such entries stay `candidate`
until auth, rate limits and the owner's OK are on an issue (README.md).

**Q10. Where would Supa Admin read it?**
MAP `Supa-admin/` is static JS (`supa-admin.js`, `flags.js`, …) with no
build step, so it cannot import Python or parse YAML easily. → Flat
`key: value` frontmatter (parseable in ten lines of JS) plus a JSON index
from `tools/skills_index.py`. Where that JSON is published is for the
floor-1 issue (Q-G).

## 3. Open questions — only the owner can answer

Asked on **looper#79**. Answers will go in
`.SEED/decisions/79-skills-registry-answers.md`.

- **Q-A. `media`:** registry-only folder, or a seventh archetype on the map
  too? Proposal: registry-only. And is "MCP server → `media/`, single
  archetype MCP tool → its archetype" the right split?
- **Q-B. Folder names:** keep the map **labels** (`stays`, `jobs`, `dining`)
  or switch to the code ids (`accommodation`, `job-offers`, `food`)?
  Proposal: keep labels; README carries the alias table.
- **Q-C. HybridCard-only archetypes** (`retail, health, trades,
  professional, creative, driver`): file their skills under the map archetype
  the end user sees (retail/trades deals → `offers`), under `platform/`, or
  add folders? Proposal: map archetype the user sees, else `platform/`.
- **Q-D. `fetch` (Fetch_Deliveries):** own folder, `platform/`, or wait
  until it joins the taxonomy?
- **Q-E. Home repo for shared skills:** when a skill is used by two or more
  repos, where does the canonical SKILL.md live — the repo where the code
  runs (proposal), or always looper as registry home?
- **Q-F. Floors:** what are the floor names for `owner_floor`? The brief
  says "floor 1" for Supa Admin. Repo names (today's default) or numbered
  floors?
- **Q-G. Who approves `candidate → approved`**, and where: a comment from
  you on the "Skill: …" issue (proposal), or something else? And where should
  the generated JSON index be published for Supa Admin?

---
name: archetype-map
form: function
archetype: platform
home_repo: localloop.pro-main
path: assets/js/category-taxonomy.js
status: candidate
owner_floor: localloop.pro-main
risk: low
why: At least six archetype vocabularies drift across the three repos; one read-only mapping table from the map taxonomy would give every floor the same labels.
---

# archetype-map (inventory top-5 #3)

A read-only `archetype-map.json` published by the map, mapping each map
taxonomy key to its registry folder and to the HybridCard archetype ids.
Inventory row B6 (`docs/skills/INVENTORY.md`, looper#72).

Pinned: looper @ `9becb9c` · map @ `13400a8` · cards @ `7a0e584`

## Evidence

- Source of truth: map `assets/js/category-taxonomy.js:2` ("single source of
  truth for archetype → sub-category"), table at
  map `assets/js/category-taxonomy.js:14`; key `Food` with label `Dining` at
  map `assets/js/category-taxonomy.js:42` and map `assets/js/category-taxonomy.js:43`.
- Copies and other vocabularies:
  map `assets/js/agent-registry.js:12` (agent definitions);
  map `workers/looper-gateway/src/index.mjs:51` to map `workers/looper-gateway/src/index.mjs:60`
  (gateway subagents, adds `fetch`, `claims`, `geo_intelligence`, `notifications`);
  looper `web/jarvis/voice-command-router.js:683` (`PIN_CATEGORIES`);
  cards `src/types/archetypes.ts:95` (`food`), cards `src/types/archetypes.ts:118` (`accommodation`);
  cards `src/lib/bridge/payload.ts:19` (`ARCHETYPE_TO_CATEGORY`), read by
  map `workers/looper-gateway/src/bridge-pin.mjs:74`.
- looper's TypeDB brain stores the raw HybridCard id:
  looper `brain/sync.py:148`. That is why the registry must not join on
  `archetype_id` without this table.

## Proposed scope

One JSON file in the map, generated from `category-taxonomy.js`, with rows
like `{ "map_key": "Food", "label": "Dining", "registry": "dining",
"cards": ["food"] }`. looper and hybridcard-v2 read it; nobody edits a copy.
Labels only: it never changes which results show or their order.

## Shared with

- localloop.pro-main (home): taxonomy, agent registry, gateway.
- looper: this registry's folder names, Jarvis `PIN_CATEGORIES`, brain sync.
- hybridcard-v2: card archetypes and the bridge category map.

## Why risk `low`

Matches inventory row B6 (low, must not reorder results). A static, public,
read-only label table. No writes, messages, money or LLM calls. It must stay
labels only: if it is ever used to rank or filter results, that is a new
entry and a new risk review.

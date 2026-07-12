# 03 — Phase 2 — The Brain: TypeDB knowledge graph (ADDITIVE)

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F2.1** — TypeDB service + geo schema
- [ ] **F2.2** — Sync worker: bridge events + SQLite → TypeDB
- [ ] **F2.3** — `/api/discover` (graph-powered search with safe fallback)
- [ ] **F2.4** — Archetype + skill graph (category assist)
- [ ] **F2.5** — Self-improving telemetry (finally write `training_log`)

> **2026-07-12 progress (see `.SEED/decisions.md`):** the FALLBACK half of
> F2.3 shipped — `GET /api/discover` (routes/discover.py) with the frozen
> response shape + `engine: "fallback"`, seed suburb table mirroring the
> voice router's, `TYPEDB_ENABLED` gate ready for the graph engine. F2.5's
> core shipped: every `/api/search` and `/api/discover` now writes
> `training_log` (intent + anonymous session id, emails/AU-mobiles scrubbed
> — services/telemetry.py; no-PII test included), so `training/export.py`
> has real data. F2.3's box ticks only after the TypeDB engine + parity
> test (needs F2.1/F2.2); F2.5's after the TypeDB DB-2 archetype counters
> (needs F2.4).

---


---

**F2.1 — TypeDB service + geo schema**

- **What:** TypeDB container (Coolify, internal-only port 1729) + schema
  001 (geo) + 002 (business) from TYPEDB-GEO-HIERARCHY-SPEC, seeded for AU:
  NSW → Sydney → Eastern-Suburbs suburbs (Bondi, Bondi Junction, Bronte,
  Rose Bay, Maroubra, …) + Byron Bay; pre-computed `nearby` relations
  (10 km default).
- **Files (looper repo):** `brain/schema/001_geo.tql`,
  `brain/schema/002_business.tql`, `brain/seed_geo.py`,
  `brain/migrate.py` (tracks applied schema files), `brain/README.md`.
- **Steps:** run TypeDB via docker (`vaticle/typedb`, database `localloop`;
  staging `localloop_staging`); define abstract `geo_region` + concrete
  world/country/state/city/suburb/locality; `located_in`, `nearby`
  (with `distance_km`); `business_entity` (owns `hybrid_card_id`,
  `source_pin_id`, name, slug, archetype_id, sub_type, tier, is_active) +
  `serves_area`, `franchise_of`, `subsidiary_of`. Seed suburbs from a
  committed CSV (name, postcode, lat, lng) — start with ~20 eastern-suburbs
  rows + Byron Bay, not all of GNAF.
- **Acceptance:** `python brain/migrate.py && python brain/seed_geo.py`
  idempotent; TypeQL query "suburbs within 5 km of Bondi" returns Bronte +
  Bondi Junction; port 1729 NOT publicly reachable.
- **Depends:** F0.4 (docker patterns); parallel-safe with Phase 1.

---

**F2.2 — Sync worker: bridge events + SQLite → TypeDB**

- **What:** Whenever a business/deal lands (F1.1/F1.2) or on nightly full
  sync, upsert the matching `business_entity` + `located_in` (nearest
  suburb by haversine over the seeded suburb list) into TypeDB. TypeDB down
  ⇒ log and continue (never block ingest — additive rule).
- **Files:** `brain/sync.py` (uses `typedb-driver` Python), hook in
  `routes/ingest.py` (fire-and-forget task via FastAPI `BackgroundTasks`),
  `brain/full_sync.py` (CLI, cron nightly).
- **Acceptance:** ingest a signed test deal → TypeDB has the business with
  `located_in Bondi`; stop TypeDB container → ingest still returns 200;
  `full_sync.py` backfills the 20 seeded businesses.
- **Depends:** F1.1, F2.1.

---

**F2.3 — `/api/discover` (graph-powered search with safe fallback)**

- **What:** New looper endpoint
  `GET /api/discover?suburb=Bondi&radius_km=5&category=food` — TypeDB
  resolves the geo set (`nearby` suburbs → businesses), SQLite hydrates
  details + reviews, ranking stays reviews+recency+proximity. If
  `TYPEDB_ENABLED=false` or TypeDB errors → transparent fallback to the
  existing haversine query (identical response shape, plus
  `"engine": "fallback"`).
- **Acceptance:** parity test: fallback vs graph return the same businesses
  for the seeded set; response includes `engine` field; anti-bias test
  passes (no discount in ordering).
- **Depends:** F2.2.

---

**F2.4 — Archetype + skill graph (category assist)**

- **What:** Schema 004: `archetype`, `archetype_sub_type`,
  `skill_definition`, relations `has_sub_type`, `provides_skill`,
  `inherits_skills`. Seed the 10 HybridCard archetypes + the per-archetype
  skill lists from ARCHETYPE-SKILL-REGISTRY-SPEC (55 skills as data — names,
  categories, NOT the prompts; prompts stay in the card repo).
  Endpoint: `GET /api/archetypes/{archetype}/skills?sub_type=…` returning
  the resolved skill set (sub-type overrides → inherited archetype skills).
- **Why:** this is how Looper "helps business category types better their
  business through their card" — it can tell any business what its card can
  do for it, and llx11/Ricky can surface it.
- **Acceptance:** `GET /api/archetypes/trades/skills?sub_type=plumber`
  returns plumber-specific + inherited trades skills, deduped; unknown
  archetype → 404.
- **Depends:** F2.1 (F2.2 not required).

---

**F2.5 — Self-improving telemetry (finally write `training_log`)**

- **What:** Log every `/api/search`, `/api/discover`, and widget/voice query
  into the existing `training_log` table (query, response summary, intent,
  session_id — NO PII, no mobile numbers) + per-archetype counters into
  TypeDB DB 2 (`workflow_telemetry` schema 005: skill/category usage counts
  by archetype). `training/export.py` then has real data → JSONL for the
  future fine-tune loop.
- **Acceptance:** 10 test queries → 10 `training_log` rows with intents;
  `python training/export.py` emits valid JSONL; a `grep`-based test proves
  no mobile numbers/emails in exports.
- **Depends:** F2.3 (F2.4 for archetype counters).

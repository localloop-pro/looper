# F2.1–F2.3 TypeDB completion evidence — 2026-08-12

This pass finished and verified the existing TypeDB work package locally. It
did **not** deploy or alter production infrastructure.

## Pinned compatibility pair

- TypeDB Core: `vaticle/typedb:2.29.1`
- Python driver: `typedb-driver==2.28.4`
- Exposure during acceptance: `127.0.0.1:1729` only

## Acceptance results

| Contract | Result |
|---|---|
| `brain/migrate.py` first run | database created; `001_geo.tql` + `002_business.tql` applied |
| migration second run | `All migrations already applied` |
| `brain/seed_geo.py` first run | 21 rows; 26 geo inserts; 378 directed nearby pairs |
| seed second run | 0 geo inserts; 0 nearby inserts |
| Bondi Beach nearby query | 19 results; includes Bronte + Bondi Junction |
| real signed deal ingest | HTTP 200; demo business linked to Bondi Beach |
| TypeDB stopped, same ingest path | HTTP 200; sync error logged and swallowed per additive rule |
| `brain/full_sync.py` | 20 SQLite businesses; 20 successful; 0 errors |
| `/api/discover` parity | fallback 20, graph 20, identical set **and order** |
| TypeDB stopped with graph enabled | HTTP 200, `engine: "fallback"`, 20 results |

## Durable regression commands

```bash
cd backend
.venv/bin/python -m pytest -q
# 80 passed, 1 skipped (the real TypeDB test is opt-in)

RUN_TYPEDB_INTEGRATION=1 TYPEDB_ADDRESS=localhost:1729 \
  .venv/bin/python -m pytest -q tests/test_typedb_integration.py
# 1 passed
```

`test_typedb_integration.py` creates and removes an isolated TypeDB database.
It proves signed ingest → `business_entity`/`located_in` and graph/fallback
parity without touching the shared `localloop` database.

## Defect fixed during acceptance

The host shell exposed `TYPEDB_ADDRESS=""`. Python's
`os.getenv("TYPEDB_ADDRESS", default)` returns that blank value instead of the
default, causing the TypeDB driver to raise `invalid format`. Every brain entry
point and graph discovery now treats a blank address/database as unset. A
second regression ensures valid zero latitude/longitude are not treated as
missing.

## Remaining production gate

Bill must approve/deploy the pinned TypeDB service on Coolify with port 1729
internal-only, set `TYPEDB_ENABLED=true`, `TYPEDB_ADDRESS`, `TYPEDB_DB`, and
register the nightly full-sync task. Repeat the query/integration smoke there
before checking F2.1–F2.3 in the authoritative feature tracker.

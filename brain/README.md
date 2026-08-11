# LOOPER Brain — TypeDB Knowledge Graph (F2.1 / F2.2)

The brain is an **additive** layer over the transactional sources of truth
(SQLite for LOOPER, Supabase for the map, MongoDB for HybridCard).  TypeDB
stores *relationships* — geo hierarchy, business-to-suburb proximity,
archetype/skill graphs — that relational DBs model awkwardly.

TypeDB being down **never** blocks any API endpoint.  Set `TYPEDB_ENABLED=false`
(the default) to skip all brain calls transparently.

## Quick-start

### 1. Install TypeDB

```bash
# Docker (recommended for Coolify)
docker run -d --name typedb -p 1729:1729 vaticle/typedb:latest

# Or: https://typedb.com/docs/home/install
```

> **Note (gotcha):** on Bill's local machine, port 8000 is already taken by a
> local TypeDB server.  The backend runs with `LOOPER_PORT=8010` locally.

### 2. Install the Python driver

```bash
pip install typedb-driver
# Pin exact version: pip index versions typedb-driver
# Record pinned version in .SEED/decisions.md
```

### 3. Run migrations

```bash
python brain/migrate.py
# → applies 001_geo.tql and 002_business.tql (idempotent)
```

To see what would be applied without touching TypeDB:

```bash
python brain/migrate.py --dry-run
```

### 4. Seed geo data

```bash
python brain/seed_geo.py
# → inserts World → AU → NSW → Sydney → 21 eastern-suburbs suburbs
# → computes nearby relations (≤ 10 km pairs)
# Idempotent: safe to re-run.
```

### 5. Enable the brain in the backend

Set `TYPEDB_ENABLED=true` in the backend's environment (`.env` or Coolify):

```
TYPEDB_ENABLED=true
TYPEDB_ADDRESS=typedb:1729      # Docker service name in Coolify; use localhost:1729 when running the backend directly on the host
```

The `GET /api/discover` endpoint will then route through the TypeDB graph
engine instead of the SQLite haversine fallback.

### 6. Nightly full sync (F2.2)

Run once after enabling to backfill existing SQLite businesses:

```bash
python brain/full_sync.py
```

Coolify Scheduled Task: `0 3 * * *` (3 AM UTC daily).

## Files

| File | Purpose |
|------|---------|
| `schema/001_geo.tql` | Geo hierarchy: World → Country → State → City → Suburb |
| `schema/002_business.tql` | Business entity + serves_area / franchise / subsidiary |
| `data/suburbs.csv` | Seed data: 21 Eastern Suburbs + Byron Bay |
| `migrate.py` | Schema migration runner (tracks applied in `.applied_migrations`) |
| `seed_geo.py` | Seeds the geo hierarchy + nearby relations |
| `sync.py` | Per-event sync (called from ingest.py as BackgroundTask) |
| `full_sync.py` | Nightly full sync CLI |

## Acceptance (F2.1)

```bash
python brain/migrate.py && python brain/seed_geo.py
# Then in the TypeDB Studio or typedb-console:
# match $a isa suburb, has name "Bondi Beach";
#   (region-a: $a, region-b: $b) isa nearby; $b has name $n; get $n;
# Expected: Tamarama, Bondi, North Bondi, Bronte, Clovelly, ...
```

## Acceptance (F2.2)

```bash
# Send a signed test deal (business lat/lng in Bondi area)
python backend/tests/send_signed_event.py
# Then verify in TypeDB Studio:
# match $b isa business_entity, has name "Test Café";
#   (contained: $b, container: $s) isa located_in; $s has name $sn; get $sn;
# Expected: a Bondi suburb
```

## TypeQL version note

Schemas are written in TypeQL 2.x compatible syntax (used with `typedb-driver`).
Verify the exact syntax against the installed TypeDB version and
TYPEDB-GEO-HIERARCHY-SPEC.md (in `new-card/planning/`) before first use.
Record the pinned package version in `.SEED/decisions.md`.

## TypeDB is NOT exposed to the internet

Port 1729 must remain internal-only (Coolify network policy, no public route).

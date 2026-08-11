"""Seed TypeDB with the LOOPER geo hierarchy.

Reads brain/data/suburbs.csv and inserts (idempotently):
  World → Country → State → City → Suburb chain with located_in relations.
  Nearby relations (≤ NEARBY_KM) between all suburb pairs.

Safe to re-run: checks entity existence before inserting.

Usage:
    python brain/seed_geo.py [--host localhost:1729] [--db localloop]

Requires: migrate.py must have been run first.
"""
import argparse
import csv
import math
import os
import sys
from pathlib import Path
from typing import NamedTuple

DATA_FILE = Path(__file__).parent / "data" / "suburbs.csv"
DEFAULT_HOST = os.getenv("TYPEDB_ADDRESS", "localhost:1729")
DEFAULT_DB = os.getenv("TYPEDB_DB", "localloop")
NEARBY_KM = 10.0


class SuburbRow(NamedTuple):
    name: str
    postcode: str
    lat: float
    lng: float
    city: str
    state: str
    country: str


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "")


def _load_csv() -> list[SuburbRow]:
    rows: list[SuburbRow] = []
    with DATA_FILE.open() as fh:
        for r in csv.DictReader(fh):
            rows.append(SuburbRow(
                name=r["name"].strip(),
                postcode=r["postcode"].strip(),
                lat=float(r["lat"]),
                lng=float(r["lng"]),
                city=r["parent_city"].strip(),
                state=r["parent_state"].strip(),
                country=r["parent_country"].strip(),
            ))
    return rows


def _existing_names(session, entity_type: str) -> set[str]:
    """Return the set of 'name' attribute values already in TypeDB for this type."""
    from typedb.driver import TransactionType  # type: ignore[import]
    names: set[str] = set()
    with session.transaction(TransactionType.READ) as tx:
        query = f'match $x isa {entity_type}, has name $n; get $n;'
        try:
            for answer in tx.query.get(query):
                concept = answer.get("n")
                # API compatibility: try .get_value() then .value
                try:
                    names.add(concept.get_value())
                except AttributeError:
                    names.add(concept.value)
        except Exception as exc:
            print(f"  error: could not read {entity_type} names: {exc}", file=sys.stderr)
            raise
    return names


def _existing_nearby_pairs(session) -> set[tuple]:
    """Return (name_a, name_b) tuples for existing nearby relations (role-ordered).

    Tracks directed pairs so both (a→b) and (b→a) are seeded independently,
    allowing TypeQL queries to find neighbors from either endpoint.
    """
    from typedb.driver import TransactionType  # type: ignore[import]
    pairs: set[tuple] = set()
    with session.transaction(TransactionType.READ) as tx:
        query = 'match (region-a: $a, region-b: $b) isa nearby; $a has name $na; $b has name $nb; get $na, $nb;'
        try:
            for answer in tx.query.get(query):
                def _val(c):  # noqa: E306
                    try:
                        return c.get_value()
                    except AttributeError:
                        return c.value
                pairs.add((_val(answer.get("na")), _val(answer.get("nb"))))
        except Exception as exc:
            print(f"  error: could not read nearby pairs: {exc}", file=sys.stderr)
            raise
    return pairs


def seed(host: str, db_name: str) -> None:
    try:
        from typedb.driver import TypeDB, SessionType, TransactionType  # type: ignore[import]
    except ImportError:
        print("ERROR: typedb-driver not installed. Run: pip install typedb-driver", file=sys.stderr)
        sys.exit(1)

    rows = _load_csv()
    print(f"Loaded {len(rows)} rows from {DATA_FILE}")

    with TypeDB.core_driver(host) as driver:
        with driver.session(db_name, SessionType.DATA) as session:
            # ── Step 1: geo entity chain ─────────────────────────────────────
            existing_worlds = _existing_names(session, "world")
            existing_countries = _existing_names(session, "country")
            existing_states = _existing_names(session, "state")
            existing_cities = _existing_names(session, "city")
            existing_suburbs = _existing_names(session, "suburb")

            inserts_made = 0
            with session.transaction(TransactionType.WRITE) as tx:
                # World (singleton)
                if "Earth" not in existing_worlds:
                    tx.query.insert(
                        'insert $w isa world, has name "Earth", has slug "earth";'
                    )
                    inserts_made += 1

                for row in rows:
                    if row.country not in existing_countries:
                        tx.query.insert(
                            f'match $w isa world, has name "Earth"; '
                            f'insert $c isa country, '
                            f'has name "{row.country}", '
                            f'has slug "{_slugify(row.country)}", '
                            f'has country_code "AU", '
                            f'has latitude -25.0, has longitude 133.0; '
                            f'(contained: $c, container: $w) isa located_in;'
                        )
                        existing_countries.add(row.country)
                        inserts_made += 1

                    if row.state not in existing_states:
                        tx.query.insert(
                            f'match $c isa country, has name "{row.country}"; '
                            f'insert $s isa state, '
                            f'has name "{row.state}", '
                            f'has slug "{_slugify(row.state)}"; '
                            f'(contained: $s, container: $c) isa located_in;'
                        )
                        existing_states.add(row.state)
                        inserts_made += 1

                    if row.city not in existing_cities:
                        tx.query.insert(
                            f'match $s isa state, has name "{row.state}"; '
                            f'insert $ci isa city, '
                            f'has name "{row.city}", '
                            f'has slug "{_slugify(row.city)}", '
                            f'has latitude {row.lat}, has longitude {row.lng}; '
                            f'(contained: $ci, container: $s) isa located_in;'
                        )
                        existing_cities.add(row.city)
                        inserts_made += 1

                    if row.name not in existing_suburbs:
                        tx.query.insert(
                            f'match $ci isa city, has name "{row.city}"; '
                            f'insert $sub isa suburb, '
                            f'has name "{row.name}", '
                            f'has slug "{_slugify(row.name)}", '
                            f'has postcode "{row.postcode}", '
                            f'has latitude {row.lat}, has longitude {row.lng}; '
                            f'(contained: $sub, container: $ci) isa located_in;'
                        )
                        existing_suburbs.add(row.name)
                        inserts_made += 1

                tx.commit()
            print(f"  geo chain: {inserts_made} inserts (0 if all existed)")

            # ── Step 2: nearby relations ─────────────────────────────────────
            # Insert both (a→b) and (b→a) so TypeQL can find neighbors from
            # either endpoint with role-specific queries like (region-a: $x).
            existing_pairs = _existing_nearby_pairs(session)
            nearby_inserts = 0
            with session.transaction(TransactionType.WRITE) as tx:
                for i, a in enumerate(rows):
                    for b in rows[i + 1:]:
                        dist = haversine(a.lat, a.lng, b.lat, b.lng)
                        if dist > NEARBY_KM:
                            continue
                        for x, y in [(a, b), (b, a)]:
                            if (x.name, y.name) in existing_pairs:
                                continue
                            tx.query.insert(
                                f'match $a isa suburb, has name "{x.name}"; '
                                f'$b isa suburb, has name "{y.name}"; '
                                f'insert (region-a: $a, region-b: $b) isa nearby, '
                                f'has distance_km {round(dist, 2)};'
                            )
                            existing_pairs.add((x.name, y.name))
                            nearby_inserts += 1
                tx.commit()
            print(f"  nearby: {nearby_inserts} directed pairs inserted (≤ {NEARBY_KM} km)")

    print("Geo seed complete.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="LOOPER TypeDB geo seeder")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--db", default=DEFAULT_DB)
    args = p.parse_args()
    seed(args.host, args.db)

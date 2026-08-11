"""F2.2 — TypeDB sync worker.

Called from backend/routes/ingest.py as a FastAPI BackgroundTask after every
successful bridge ingest.  TypeDB being unreachable or TYPEDB_ENABLED=false
never blocks ingest — this is additive (TYPEDB-GEO-HIERARCHY-SPEC §4).

Public API (used by ingest.py and full_sync.py):
    sync_business(hybrid_card_id, name, category, lat, lng, is_active,
                  archetype_id=None, sub_type=None)

Internally:
  • Finds the nearest suburb by haversine over brain/data/suburbs.csv.
  • Upserts the business_entity in TypeDB (delete-old-attrs + insert-new).
  • Links it to the nearest suburb via located_in.
  • TypeDB errors are caught and logged; they NEVER propagate.
"""
from __future__ import annotations

import csv
import logging
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUBURBS_CSV = Path(__file__).parent / "data" / "suburbs.csv"
_TYPEDB_ENABLED = os.getenv("TYPEDB_ENABLED", "false").lower() == "true"
_TYPEDB_HOST = os.getenv("TYPEDB_ADDRESS", "localhost:1729")
_TYPEDB_DB = os.getenv("TYPEDB_DB", "localloop")
_MAX_SUBURB_KM = 100.0  # skip sync for businesses more than 100 km from any seeded suburb


# ── Suburb lookup (haversine nearest) ────────────────────────────────────────

class _SuburbEntry:
    __slots__ = ("name", "lat", "lng")

    def __init__(self, name: str, lat: float, lng: float):
        self.name = name
        self.lat = lat
        self.lng = lng


@lru_cache(maxsize=1)
def _load_suburbs() -> list[_SuburbEntry]:
    entries: list[_SuburbEntry] = []
    try:
        with SUBURBS_CSV.open() as fh:
            for row in csv.DictReader(fh):
                try:
                    entries.append(_SuburbEntry(
                        name=row["name"].strip(),
                        lat=float(row["lat"]),
                        lng=float(row["lng"]),
                    ))
                except (KeyError, ValueError):
                    pass
    except FileNotFoundError:
        logger.warning("brain/data/suburbs.csv not found — nearest-suburb lookup disabled")
    return entries


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))


def nearest_suburb(lat: float, lng: float) -> Optional[str]:
    """Return the name of the nearest suburb from suburbs.csv, or None.

    Returns None if the nearest suburb is more than _MAX_SUBURB_KM away —
    prevents overseas / interstate businesses being assigned to a Sydney suburb.
    """
    suburbs = _load_suburbs()
    if not suburbs:
        return None
    best = min(suburbs, key=lambda s: _haversine(lat, lng, s.lat, s.lng))
    if _haversine(lat, lng, best.lat, best.lng) > _MAX_SUBURB_KM:
        return None
    return best.name


# ── TypeDB helpers ────────────────────────────────────────────────────────────


def _tql_escape(value: str) -> str:
    """Escape a string for safe interpolation inside TypeQL double-quoted literals."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _get_driver():
    from typedb.driver import TypeDB  # type: ignore[import]
    return TypeDB.core_driver(_TYPEDB_HOST)


def _concept_value(concept) -> str | bool | int | float | None:
    """Extract primitive value from a TypeDB concept (API-version-agnostic)."""
    try:
        return concept.get_value()
    except AttributeError:
        try:
            return concept.value
        except AttributeError:
            return None


def _business_exists(session, hybrid_card_id: str) -> bool:
    from typedb.driver import TransactionType  # type: ignore[import]
    with session.transaction(TransactionType.READ) as tx:
        results = list(tx.query.get(
            f'match $b isa business_entity, has hybrid_card_id "{hybrid_card_id}"; get $b; limit 1;'
        ))
        return len(results) > 0


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "")


def _upsert_business(session, *, hybrid_card_id: str, name: str,
                     category: str, lat: float | None, lng: float | None,
                     is_active: bool, archetype_id: Optional[str],
                     sub_type: Optional[str]) -> None:
    """Insert or update a business_entity in TypeDB."""
    from typedb.driver import TransactionType  # type: ignore[import]

    # Escape all string values before TypeQL interpolation
    hid_e = _tql_escape(hybrid_card_id)
    name_e = _tql_escape(name)
    slug_e = _tql_escape(_slugify(name))
    arch_e = _tql_escape(archetype_id or category or "other")
    sub_e = _tql_escape(sub_type or "")

    with session.transaction(TransactionType.WRITE) as tx:
        if _concept_value is not None and _business_exists(session, hybrid_card_id):
            # Delete mutable attributes before re-inserting (TypeDB 2.x update pattern)
            tx.query.delete(
                f'match $b isa business_entity, has hybrid_card_id "{hid_e}", '
                f'has name $n, has slug $sl, has archetype_id $ai, '
                f'has sub_type $st, has is_active $ia; '
                f'delete $b has name $n; $b has slug $sl; $b has archetype_id $ai; '
                f'$b has sub_type $st; $b has is_active $ia;'
            )
            if lat is not None:
                tx.query.delete(
                    f'match $b isa business_entity, has hybrid_card_id "{hid_e}", '
                    f'has latitude $la, has longitude $lo; '
                    f'delete $b has latitude $la; $b has longitude $lo;'
                )
            tx.query.insert(
                f'match $b isa business_entity, has hybrid_card_id "{hid_e}"; '
                f'insert $b has name "{name_e}", has slug "{slug_e}", '
                f'has archetype_id "{arch_e}", has sub_type "{sub_e}", '
                f'has is_active {str(is_active).lower()}'
                + (f', has latitude {lat}, has longitude {lng}' if lat is not None else '')
                + ';'
            )
        else:
            # New entity
            attrs = (
                f'has hybrid_card_id "{hid_e}", '
                f'has name "{name_e}", has slug "{slug_e}", '
                f'has archetype_id "{arch_e}", has sub_type "{sub_e}", '
                f'has tier "premium", has is_active {str(is_active).lower()}'
            )
            if lat is not None and lng is not None:
                attrs += f', has latitude {lat}, has longitude {lng}'
            tx.query.insert(f'insert $b isa business_entity, {attrs};')
        tx.commit()


def _link_suburb(session, hybrid_card_id: str, suburb_name: str) -> None:
    """Create a located_in relation from the business_entity to the suburb
    (if one does not already exist)."""
    from typedb.driver import TransactionType  # type: ignore[import]

    # Check if located_in already exists for this business
    with session.transaction(TransactionType.READ) as tx:
        existing = list(tx.query.get(
            f'match $b isa business_entity, has hybrid_card_id "{hybrid_card_id}"; '
            f'$s isa suburb, has name "{suburb_name}"; '
            f'(contained: $b, container: $s) isa located_in; '
            f'get $b; limit 1;'
        ))
    if existing:
        return

    # Remove any stale located_in for this business before adding new one
    with session.transaction(TransactionType.WRITE) as tx:
        tx.query.delete(
            f'match $b isa business_entity, has hybrid_card_id "{hybrid_card_id}"; '
            f'$r (contained: $b) isa located_in; '
            f'delete $r isa located_in;'
        )
        tx.query.insert(
            f'match $b isa business_entity, has hybrid_card_id "{hybrid_card_id}"; '
            f'$s isa suburb, has name "{suburb_name}"; '
            f'insert (contained: $b, container: $s) isa located_in;'
        )
        tx.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def sync_business(
    hybrid_card_id: str,
    name: str,
    category: str,
    lat: Optional[float],
    lng: Optional[float],
    is_active: bool,
    *,
    archetype_id: Optional[str] = None,
    sub_type: Optional[str] = None,
) -> bool:
    """Upsert one business into TypeDB.  Never raises — TypeDB errors are
    logged and swallowed so the caller (ingest route) always succeeds.

    Returns True on success, False if the sync was skipped or failed.
    """
    if not _TYPEDB_ENABLED:
        return True  # disabled is not an error

    try:
        from typedb.driver import SessionType  # type: ignore[import]
    except ImportError:
        logger.debug("typedb-driver not installed; skipping brain sync")
        return False

    suburb = nearest_suburb(lat, lng) if (lat and lng) else None

    try:
        with _get_driver() as driver:
            with driver.session(_TYPEDB_DB, SessionType.DATA) as session:
                _upsert_business(
                    session,
                    hybrid_card_id=hybrid_card_id,
                    name=name,
                    category=category,
                    lat=lat,
                    lng=lng,
                    is_active=is_active,
                    archetype_id=archetype_id,
                    sub_type=sub_type,
                )
                if suburb:
                    _link_suburb(session, hybrid_card_id, suburb)
        return True
    except Exception as exc:
        # ADDITIVE RULE: TypeDB down ≠ ingest failure.
        logger.warning("TypeDB sync failed for %s: %s", hybrid_card_id, exc)
        return False

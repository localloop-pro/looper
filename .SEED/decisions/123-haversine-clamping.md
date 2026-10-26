# Issue #123: Clamp haversine intermediate value to prevent antipodal ValueError

**Status:** RESOLVED

## Decision

Added clamping of intermediate value `a` to `[0, 1]` in the haversine distance calculation before computing square roots.

## Why

Floating-point rounding errors for antipodal or near-antipodal coordinates can produce `a > 1.0000...0001`, causing `math.sqrt(1 - a)` to raise `ValueError: math domain error`. After PR#122 (which scans all candidates before result limit), even an off-page antipodal business outside the requested radius can trigger the 500 error.

## How (Implementation)

**File:** `backend/routes/search.py:15-27`

**Change:** Added `a = max(0.0, min(1.0, a))` before computing square roots.

```python
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two lat/lng points in km.
    
    Clamps intermediate value to [0, 1] to avoid ValueError from floating-point
    rounding at antipodal or near-antipodal coordinates (issue #123).
    """
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    a = max(0.0, min(1.0, a))
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
```

## Scope

- **No changes to:** ranking, response format, earth radius, coordinate validation, authentication, rate limiting
- **Preserves:** zero distance accuracy, existing batched query budgets, ordering invariants
- **Regression test:** `backend/tests/test_search_haversine_antipodal.py` with 10 tests including antipodal pairs

## Verification

- All 790 backend tests pass (including 91 search tests + 10 new antipodal tests)
- Direct unit tests confirm antipodal coordinates (0,0) to (0,180) return finite 20015 km distance
- Integration tests confirm /search and /businesses endpoints return 200 with nearby matches when antipodal candidates exist outside radius

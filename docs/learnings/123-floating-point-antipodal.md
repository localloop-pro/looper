# Floating-point rounding in haversine distance calculations

## What happened

The haversine formula computes great-circle distance between two points on Earth using intermediate value `a = sin²(Δlat/2) + cos(lat1)cos(lat2)sin²(Δlng/2)`. Mathematically, `a` is always in `[0, 1]`. However, floating-point rounding errors can produce `a = 1.0000000000000002` for coordinates at or near antipodal points (opposite sides of Earth).

When `a > 1.0`, `sqrt(1 - a)` raises `ValueError: math domain error`.

## Why it matters

**Before PR#122:** The search endpoint filtered candidates by distance THEN applied the result limit, so an antipodal database entry wouldn't be evaluated if it fell outside the top N results by relevance.

**After PR#122:** The endpoint scans ALL candidates before the result limit, so even an off-page antipodal business (20,000+ km away) gets its distance computed. If no clamping exists, valid user queries trigger 500 errors.

Example: Searching for "vet" in Bondi Beach with a 5 km radius. If the database contains a business (accidentally) at the antipode of Sydney's coordinates, the request 500s even though the antipodal business is filtered out anyway.

## The fix

Clamp `a` to `[0, 1]` before taking square roots:

```python
a = max(0.0, min(1.0, a))
```

This is numerically safe because:
1. The rounding error is vanishingly small (ULP of 1.0)
2. For true antipodal points, `a` is genuinely exactly 1.0, and `sqrt(1 - a)` yields 0, giving infinite distance (correctly: 20,015 km)
3. For coincident points, `a` is exactly 0.0 and remains unaffected
4. All intermediate distances are preserved to rounding precision

## Test coverage

See `backend/tests/test_search_haversine_antipodal.py`:
- Direct unit tests for antipodal pairs: (0,0)→(0,180), poles, Sydney↔London antipode
- Integration tests with /search and /businesses endpoints containing antipodal candidates
- Parameterized tests over 4 antipodal coordinate pairs
- Verification that nearby, coincident, and very-close points remain accurate

## Related issues

- Issue #123: Clamp haversine rounding so valid antipodal business searches cannot return 500
- PR #122: fix(search): select eligible businesses before result limit
- PR #122 review comment: https://github.com/localloop-pro/looper/pull/122#discussion_r4373188904

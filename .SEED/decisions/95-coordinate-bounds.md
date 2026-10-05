# 95 — Public read endpoints validate coordinates at the Query boundary

Decision (2026-10-03): `/api/search`, `/api/businesses`, `/api/discover`,
`/api/pins` and `/api/tourist-info` take `lat`/`lng` from
`backend/routes/params.py`: finite only (`allow_inf_nan=False`), -90..90 and
-180..180. `radius_km` on `/api/businesses` and `/api/pins` is >0 and at most
`MAX_RADIUS_KM` (5000, the `/api/search` maximum). `/api/businesses` `limit`
is at least 1. Bad values get FastAPI's normal 422.

Why: an unchecked `lat=inf` reached `haversine_km` and returned a 500. The
check sits at the boundary so `haversine_km`, ranking and response shapes do
not change. `/api/search` and `/api/discover` keep their own (tighter)
`radius_km` bounds. Optional coordinates stay optional;
`/api/tourist-info` still requires them.

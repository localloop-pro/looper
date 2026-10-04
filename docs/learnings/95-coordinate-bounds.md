# #95 — Bad coordinates are a 422 at the Query boundary, not a 500 (2026-10-03)

`GET /api/search?q=vet&lat=inf&lng=1` crashed in `haversine_km` with a 500,
and `lat=999` was accepted. Five public read endpoints had bare `float`
query params.

Lessons:
- FastAPI parses query floats with Pydantic, which accepts "inf", "nan",
  "Infinity" and overflows "1e309" to inf. A plain `float` param is not a
  number you can do maths on yet.
- Put the rule in one place (`backend/routes/params.py`: `Latitude`,
  `Longitude`, `OptionalLatitude`, `OptionalLongitude`, `RadiusKm`) as
  `Annotated[float, Query(...)]` aliases. Each endpoint just names the type,
  so the next endpoint can't forget a bound.
- Optional params need the `None` inside the Annotated
  (`Annotated[float | None, Query(...)]`, default `= None` on the
  parameter), not `Latitude | None`, or FastAPI may not see the Query.
- Set `allow_inf_nan=False` even with `ge`/`le`: the bounds reject NaN today
  only as a side effect, and the explicit flag gives a clear
  `finite_number` error.
- Validating at the boundary keeps `haversine_km`, ranking and response
  shapes untouched, so existing tests prove nothing else moved.
- Don't stop a local server with `pkill -f "python main.py"` on a shared
  machine: it matches teammates' servers too. Kill your own PID.

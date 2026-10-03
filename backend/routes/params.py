"""LOOPER API — shared query-parameter types for public read endpoints (looper#95).

``float()`` accepts "inf", "nan" and "1e309" (overflows to inf), and
``haversine_km`` raises on a non-finite latitude, so an unchecked ``lat``
was a 500. These types reject non-finite and out-of-range values at the
Query boundary, so FastAPI answers with its normal 422 before the route runs.

``allow_inf_nan=False`` is set on purpose. Today the ``ge``/``le`` bounds
also reject NaN, but only as a side effect ("less_than_equal"); the explicit
flag gives a clear "finite_number" error and doesn't rely on that detail.
"""
from typing import Annotated

from fastapi import Query

# Largest radius any public read endpoint accepts (same as /api/search).
MAX_RADIUS_KM = 5000.0

_LAT = Query(ge=-90.0, le=90.0, allow_inf_nan=False, description="Latitude, -90..90")
_LNG = Query(ge=-180.0, le=180.0, allow_inf_nan=False, description="Longitude, -180..180")
_RADIUS = Query(gt=0, le=MAX_RADIUS_KM, allow_inf_nan=False,
                description="Radius in km, more than 0 and at most 5000")

# Required: ``lat: Latitude``. Optional: ``lat: OptionalLatitude = None``.
Latitude = Annotated[float, _LAT]
Longitude = Annotated[float, _LNG]
OptionalLatitude = Annotated[float | None, _LAT]
OptionalLongitude = Annotated[float | None, _LNG]
# Default goes on the parameter: ``radius_km: RadiusKm = 10.0``.
RadiusKm = Annotated[float, _RADIUS]

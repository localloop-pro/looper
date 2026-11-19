# 157 — Bound map pin reads

Map pins default to 100 results, with a requested limit from 1 to 500. For
coordinate searches, SQL applies a conservative spherical bounding box before
the existing exact haversine filter and proximity sort; slicing earlier could
discard nearer pins. The box wraps the antimeridian and covers all longitudes
when the search reaches a pole. Without coordinates, SQL applies the limit.
The response retains its existing fields and count describes returned pins.

The geographic query can still examine many pins in a densely populated box;
the cap bounds the response, not all candidate processing. No schema or index
change is included.

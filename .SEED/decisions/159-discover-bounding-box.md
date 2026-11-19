### Discovery candidate filtering (looper#159)

The SQLite fallback narrows candidates with a conservative spherical bounding box and the existing longest-known-suburb rule for businesses missing coordinates. The existing haversine calculation remains the final radius test, and review-based ranking is unchanged. The box wraps at the antimeridian and does not constrain longitude when the search reaches a pole. Category and unknown-suburb filters already ran in SQL. No schema or index changes are required.

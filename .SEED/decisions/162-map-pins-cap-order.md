# 162 — Map pin cap: exact-distance cut, newest first, bounded writes

Decision (2026-11-20), follow-up to #160:

- `GET /api/pins` with coordinates sorts by the exact haversine distance and
  only then rounds `distance_km` for the response, so `limit` never keeps a
  farther pin that rounds to the same 0.1 km.
- Without coordinates it returns the newest pins first
  (`created_at DESC, id DESC`) before `limit`, so new pins are not hidden
  behind the first 100 rows. Ordering stays verifiable-only (proximity,
  recency); response shape `{count, pins}` is unchanged.
- `POST /api/pins` rejects `lat` outside -90..90 and `lng` outside -180..180
  (and non-finite values) with 422, the same bounds as the read params (#95).

Existing data is not rewritten. Out-of-range rows written before this change
are no longer found by the #160 bounding box. Bill can count them on a
**backup copy** (never the live DB), read-only:

```bash
sqlite3 -readonly ~/looper-backups/looper-<UTC>.db \
  "SELECT COUNT(*) FROM map_pins WHERE lat NOT BETWEEN -90 AND 90 OR lng NOT BETWEEN -180 AND 180;"
```

Expect `0`. Any fix to such rows is a data change and needs the owner.

Not done: there is no index on `map_pins(lat, lng)`, so SQLite still scans
the table and a large radius loads most rows before the cap. An index is a
migration (hot zone); add it only with the owner.

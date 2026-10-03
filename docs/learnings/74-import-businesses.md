# #74 — Owner-verified CSV import: dry run by default (2026-10-03)

`backend/scripts/import_businesses.py --csv PATH --db URL [--apply]` lets the
owner fill the empty production brain (BLIND-SPOTS §3.2) from businesses
they checked themselves, without seed.py and without a schema change.

Lessons:
- Make the safe path the default. A missing `--apply` means a dry run that
  does the same validation and dedupe work and then rolls back, so the dry-run
  numbers are the numbers `--apply` will produce.
- `create_engine("sqlite:///missing.db")` creates the file on first connect.
  Check the file exists first (exit 2), and refuse a DB without a
  `businesses` table instead of calling `create_all`.
- Dedupe on a normalised key: `fold_accents` + whitespace collapse on both the
  existing rows and the CSV rows, and add each new key to the seen-set so
  duplicates *inside* one CSV insert once. Include inactive rows, so the import
  never re-adds a business that `card.removed` switched off.
- Python `float()` accepts `nan`, `inf` and `1e309`. Check `math.isfinite`
  before range checks, and use an Australia box to catch swapped lat/lng or a
  dropped minus sign.
- Search sorts by `distance_km or 999`, so a business at exactly the
  caller's point (distance 0.0, rounded to `None`) counts as unknown
  distance. Keep test coordinates off the query point, or the ranking test
  ends up measuring that quirk instead of the import.
- Prove "no ranking change" by flipping `source` on every row and checking
  the `/api/search` order doesn't move.

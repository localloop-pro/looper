### Owner-verified business import: insert-only, dry run by default (2026-10-03, looper#74)

- `backend/scripts/import_businesses.py --csv PATH --db SQLALCHEMY_URL [--apply]`.
  No route, no schema change, no new dependency. Dry run unless `--apply`;
  one transaction per run.
- Inserted rows: `source="owner_verified"` (existing String column),
  `is_verified=False`, `is_active=True`, no `hybrid_card_id`. `is_verified`
  stays False: the owner checked the listing exists, which is not the
  verified-review/claim meaning of that flag elsewhere.
- Dedupe key: `fold_accents` + whitespace collapse of (name, suburb), against
  every existing row (any source, active or inactive) and earlier CSV rows.
  A match is skipped, never updated, never reactivated.
- Validation: name, category, suburb, lat, lng required; lat/lng finite and in
  lat -44..-9, lng 112..154.5 (mainland + Tasmania; Lord Howe and Norfolk
  excluded until needed); website `https://` with a nonempty `hostname` (a URL `urlparse` cannot
  parse is a row rejection, not a crash), or empty; text
  lengths within the model's String sizes. Bad rows are rejected with a
  reason; the run continues.
- Exit 2 (nothing created) for a missing SQLite file, a DB without a
  `businesses` table, or a CSV header without the required columns.
- Template `docs/templates/businesses.csv` is header-only. No example
  businesses anywhere in the repo; test rows exist only inside the test file.
- Rollback: restore the pre-import backup (RUNBOOK-BACKUP-RESTORE §3,
  docs/RUNBOOK-IMPORT-BUSINESSES.md §6). No `WHERE source='owner_verified'`
  shortcut: `source` is shared by every import, so it would also hide earlier
  imports (QA, PR #103). Never delete.

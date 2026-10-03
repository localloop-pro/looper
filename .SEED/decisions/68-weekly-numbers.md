### Weekly numbers: owner-run, read-only, against a backup (2026-10-03, looper#68)

- `backend/scripts/weekly_numbers.py --db <file> [--days 7] [--json]` reads
  `training_log`, `bridge_events` and current totals from a `mode=ro`
  connection. No route, no write, no new dependency. Exit 2 if the file is
  missing (nothing created).
- "Search" = a `training_log` row whose `query_text` does not start with
  `discover suburb=` (discover logs that synthetic query). Callers pass
  free-form `intent` values (voice, search, ...), so intent can't define it.
  Zero-result = search row whose `response_text` ends in ` []`
  (routes/search.py).
- Zero-result texts are lowercased + trimmed, listed only at >= 2 repeats,
  top 10, `scrub_pii()` re-applied on output. Totals count only active
  businesses (with a non-empty `hybrid_card_id` for the card count), public
  reviews, active pins not yet expired, active deals.
- The owner runs it on the newest backup (docs/RUNBOOK-BACKUP-RESTORE.md §5).
  Agents never run it against production.

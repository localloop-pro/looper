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
- Zero-result texts are Unicode-lowercased + trimmed, listed only at >= 2 repeats,
  top 10, `scrub_pii()` re-applied on output. Totals count only active
  businesses (with a non-empty `hybrid_card_id` for the card count), public
  reviews, active pins not yet expired, active deals.
- The owner runs it on the newest backup (docs/RUNBOOK-BACKUP-RESTORE.md §5).
  Agents never run it against production.

### PR #77 QA round 1 corrections

- Intent export uses a fixed vocabulary: `search`, `voice`, `discover`,
  `(none)` for empty labels, and `other` for every other caller label.
  Group after classification so collapsed labels retain all counts in both
  windows. This deliberately loses custom intent detail to avoid exporting
  names or contact details that a regex might miss. Stored rows are unchanged.
- Connection-local Python SQL functions provide Unicode lowercasing and
  intent classification without schema changes. `CAFÉ` and `café` count as
  two occurrences of `café`; the repetition threshold stays before redaction.
- Shared `services/pii.py` depends only on `re`. Telemetry re-exports
  `scrub_pii` for existing callers; the report imports the pure module directly.
  No ORM or application engine is imported by the standalone command.
- Scope remains issue #68, read-only report corrections; QA re-test and CI
  are pending after push. No deployment or production database access.

### Validation before push

- Backend: 321 passed, 1 skipped (TypeDB server unavailable); report tests: 10 passed.
- `python3 -S scripts/weekly_numbers.py --help`: exit 0. Regression tests
  also run text and JSON with `-S` and verify unchanged database bytes.
- Router: 183 passed; Jarvis sync: 15 passed; Worker: 16 passed.
- Desktop typecheck/build passed; 47 tests passed. Compose config and
  Wrangler deploy dry run passed; local Wrangler dev started with
  `--compatibility-date 2026-05-28`, then stopped without upstream requests.
- Docker build could not run: Docker daemon unavailable. Shared Playwright
  navigation failed with closed page/context/browser; no browser acceptance
  claimed. Preview health passed on port 5675 and the preview was stopped.
- The initial full suite/npm run hit ENOSPC. After removing only this
  worktree's generated partial node_modules, both reruns passed.
- Featured spec/todo/done files are absent in this repo. Issue #68 and this
  per-issue decision track the corrections; external QA/CI remain pending.

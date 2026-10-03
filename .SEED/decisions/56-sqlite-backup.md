### SQLite backup: online backup API, owner-run, separate volume (2026-10-02, looper#56)

- `backend/scripts/sqlite_backup.py` copies with `Connection.backup(pages=-1)`
  from a `mode=ro` URI connection: one consistent snapshot under a read lock,
  never a file copy, and the source can't be written. Copy goes to a hidden
  `.partial` file, passes `PRAGMA integrity_check`, then gets renamed, so a
  failed run leaves nothing that looks like a good backup.
- Retention (`--keep`, default 14) only deletes names matching
  `looper-YYYYMMDDTHHMMSSZ.db` in `--out-dir`. It refuses an `--out-dir` equal
  to the live DB's folder (`/app/data` also holds the Kaspa cache).
- The script is standalone (no `models` import), so it never binds the app's
  engine or runs `create_all` on the source.
- Backups contain `users` PII: `.gitignore` gains `looper-*.db` and `backups/`.
- The owner wires the Coolify scheduled task and the second volume
  (`docs/RUNBOOK-BACKUP-RESTORE.md`). Agents never run it against production.

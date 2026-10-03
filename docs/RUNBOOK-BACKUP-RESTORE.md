# Runbook: back up and restore the Looper database

Who runs this: **Bill (the owner).** Agents never run it against production.

Looper keeps all its data in one SQLite file, `/app/data/looper.db`, on the
`looper-data` Docker volume of the `looper-api` app in Coolify. Until now
there was no copy anywhere (BLIND-SPOTS §3.12). This runbook gives you:

1. a daily backup (section 2),
2. a restore you can do in about five minutes (section 3),
3. a monthly restore test so you know the backups really work (section 4),
4. a weekly numbers report read from the newest backup (section 5).

The tool is `backend/scripts/sqlite_backup.py`. It is already inside the
Docker image at `/app/looper/backend/scripts/sqlite_backup.py`.

---

## 1. Keep backups private

Every backup is a full copy of the database. **It contains raw first names
and mobile numbers from the `users` table.** So:

- Never commit a backup to git, never attach one to a GitHub issue, never
  paste one into a chat. (`.gitignore` already ignores `looper-*.db` and
  `backups/`, but don't rely on that.)
- Keep backups on a volume or storage only you can read.
- If you copy a backup to your Mac, put it in a private folder and delete it
  when you're done.

The script's own output is safe to share: one line with the file name, its
size, and table and row counts. It never prints row data.

---

## 2. Set up the daily backup (once)

### 2a. Add a second volume for backups

A backup on the same volume as the database dies with it, so use a separate
one. In Coolify:

1. Open the **looper-api** application, then **Persistent Storage**.
2. Click **+ Add**, choose **Volume Mount**.
   - Name: `looper-backups`
   - Destination path: `/app/backups`
3. Save, then **Redeploy** so the container sees the new mount.

(Better still, later: also copy `/app/backups` off the box, for example a
nightly `rclone copy` or `rsync` from the server to private cloud storage.
A volume on the same server does not survive losing the server.)

### 2b. Add the scheduled task

In Coolify, open **looper-api**, then **Scheduled Tasks**, then **+ Add**:

| Field     | Value |
|-----------|-------|
| Name      | `sqlite-backup` |
| Command   | `python /app/looper/backend/scripts/sqlite_backup.py --out-dir /app/backups --keep 14` |
| Frequency | `0 3 * * *` (every day at 03:00 server time) |
| Container | `looper-api` |

`LOOPER_DB_URL` is already set inside the image
(`sqlite:////app/data/looper.db`), so the command needs nothing else.

### 2c. Run it once by hand and check it

In Coolify, open **looper-api**, then **Terminal**, and paste:

```bash
python /app/looper/backend/scripts/sqlite_backup.py --out-dir /app/backups --keep 14
ls -l /app/backups
```

Expect one line like:

```
backup ok file=looper-20261002T030000Z.db bytes=65536 tables=7 rows=32 integrity=ok kept=1 removed=0 seconds=0.01
```

and one `looper-<date>.db` file in the listing. Anything starting with
`backup FAILED:` means no backup was made: read the reason on that line.

What the script does, so you can trust it:

- It opens the live database **read-only** and copies it with SQLite's
  online backup API. The app can keep running and writing while it works.
- It checks the copy with `PRAGMA integrity_check` before keeping it.
- It keeps the newest 14 copies and deletes older ones. It only ever deletes
  files named `looper-<date>.db` inside `/app/backups`. Nothing else.
- It refuses to write into the live database's own folder (`/app/data`).

---

## 3. Restore from a backup

Use this when the database is damaged, or a change went wrong and you need
yesterday's data back. Everything written after the backup is lost, so pick
the newest backup from before the problem.

### 3a. Pick the backup

In **looper-api → Terminal**:

```bash
ls -l /app/backups
```

Names are UTC times: `looper-20261002T030000Z.db` is 2 Oct 2026, 03:00 UTC.
Check the one you picked is healthy (expect `ok`):

```bash
python -c "import sqlite3,sys; print(sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True).execute('PRAGMA integrity_check').fetchone()[0])" /app/backups/looper-20261002T030000Z.db
```

(Replace the file name with yours, here and in step 3c.)

### 3b. Stop the app

In Coolify, open **looper-api** and click **Stop**. Wait until it shows
stopped. The database file must not be written while you swap it.

### 3c. Swap the file in

The app is stopped, so use a throwaway container that mounts both volumes.
On the server (Coolify → **Servers → your server → Terminal**, or SSH):

```bash
# Find the real volume names (they carry a Coolify prefix):
docker volume ls | grep -E 'looper-(data|backups)'
```

Put those two names into the command below and run it:

```bash
docker run --rm \
  -v <looper-data volume name>:/app/data \
  -v <looper-backups volume name>:/app/backups \
  python:3.12-slim sh -c '
    set -e
    cd /app/data
    mv looper.db looper.db.before-restore-$(date -u +%Y%m%dT%H%M%SZ)
    rm -f looper.db-journal looper.db-wal looper.db-shm
    cp /app/backups/looper-20261002T030000Z.db looper.db
    ls -l /app/data'
```

The broken file is **kept** as `looper.db.before-restore-<time>`, so this
step can be undone (see 3f). Nothing is deleted.

### 3d. Start the app

In Coolify, click **Start** (or **Restart**) on **looper-api** and wait for
it to show healthy.

### 3e. Verify

From your Mac:

```bash
curl -s https://api.localloop.ai/health
```

Expect: `{"status":"healthy", ...}`

```bash
curl -s "https://api.localloop.ai/api/search?q=cafe" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['results']), 'results')"
```

Expect a number above 0, for example `3 results`. If you get `0 results` or
an error, go to 3f.

### 3f. Undo a restore

Stop the app, then run the same `docker run` as in 3c but with this inside
the quotes:

```bash
cd /app/data && mv looper.db looper.db.failed-restore && cp looper.db.before-restore-<time> looper.db
```

Start the app again and repeat 3e.

---

## 4. Monthly restore test (15 minutes, first Monday of the month)

A backup you have never restored is a hope, not a backup. Once a month,
restore the newest backup **somewhere that is not production** and check it.

On the server terminal:

```bash
docker run --rm \
  -v <looper-backups volume name>:/app/backups:ro \
  python:3.12-slim python -c "
import glob, sqlite3
f = sorted(glob.glob('/app/backups/looper-*.db'))[-1]
c = sqlite3.connect('file:' + f + '?mode=ro', uri=True)
print(f, c.execute('PRAGMA integrity_check').fetchone()[0])
for (t,) in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name\"):
    print(t, c.execute(f'SELECT COUNT(*) FROM \"{t}\"').fetchone()[0])
"
```

Check:

- [ ] The newest file is from today or yesterday (the daily task is running).
- [ ] The second line says `ok`.
- [ ] `businesses` and `reviews` counts look like the real numbers (not 0,
      not far below last month's).
- [ ] Write the date and the `businesses` count in your ops notes.

If any box fails, the daily backup is broken: run 2c by hand and read the
`backup FAILED:` reason.

Want the full drill on your Mac (app really serving the restored data)?
Download the newest backup to a private folder, then from the repo:

```bash
cd backend
LOOPER_DB_URL=sqlite:////full/path/to/looper-20261002T030000Z.db LOOPER_PORT=8010 .venv/bin/python main.py
# in a second terminal:
curl -s localhost:8010/health
curl -s "localhost:8010/api/search?q=cafe" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['results']), 'results')"
```

Stop the server with Ctrl+C and delete the downloaded file afterwards.

---

## 5. Weekly numbers (5 minutes, every Monday)

One read-only command turns the newest backup into a few numbers: queries,
distinct sessions, the zero-result rate, what people asked for that found
nothing, bridge events by status, and current business/review/pin/deal
counts, each with the previous week next to it (looper#68). It opens the file
read-only and never changes or creates anything. Run it against a **backup**,
never the live `/app/data/looper.db`. Agents never run it against production.

In Coolify, open a terminal on the `looper-api` container and run:

```bash
ls -t /app/backups/looper-*.db | head -1          # newest backup
python /app/looper/backend/scripts/weekly_numbers.py --db "$(ls -t /app/backups/looper-*.db | head -1)"
```

Or on your Mac, against a backup you downloaded to a private folder:

```bash
cd backend
python3 scripts/weekly_numbers.py --db /full/path/to/looper-20261002T030000Z.db
python3 scripts/weekly_numbers.py --db /full/path/to/looper-20261002T030000Z.db --days 30
python3 scripts/weekly_numbers.py --db /full/path/to/looper-20261002T030000Z.db --json
```

This command needs only Python's standard library. Verify without installed
packages (expected: usage text, exit 0):

```bash
python3 -S scripts/weekly_numbers.py --help
```

How to read it:

- **Zero-result searches** is the share of searches that returned nothing.
  The list under it ("Asked for, found nothing") is what to fix or onboard
  next. A text only shows up once two or more searches asked for it, so
  one-off free text never appears; emails and mobiles show as `[email]` /
  `[mobile]`.
- **By intent** exports only `search`, `voice`, `discover`, `(none)` and
  `other`. Custom caller labels are combined under `other`, including labels
  containing names, emails or mobiles. Their counts are preserved.
- Repeated queries use Unicode lowercasing: `CAFÉ` and `café` appear as
  `2x café` when both are in the same window.
- **Bridge events** counts HybridCard events by status. Anything other than
  `processed` or `stale_skipped` needs a look.
- Exit code 2 with `no database file at ...` means the path is wrong;
  nothing was created.

Intent labels never export arbitrary caller text. Query texts still contain
free text after email/mobile redaction; review them before sharing the report.

To roll back the PR #77 QA corrections in source, run from the repo root:

```bash
git revert <QA-fix-commit>
```

Expected: a new revert commit; no database changes. Reverting restores the
known report privacy and Unicode defects, so stop sharing reports until a
replacement fix is accepted.

---

## 6. Remove this (rollback)

Delete the Coolify scheduled task, then delete
`backend/scripts/sqlite_backup.py`, `backend/tests/test_sqlite_backup.py`,
`backend/scripts/weekly_numbers.py`, `backend/tests/test_weekly_numbers.py`
and this file. Nothing in the app imports either script.

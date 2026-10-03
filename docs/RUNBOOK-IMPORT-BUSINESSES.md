# Runbook: import businesses you have verified yourself

Who runs this: **Bill (the owner)**, only after choosing option 2 in
`plans/BLIND-SPOTS-2026-09-08.md` §5 step 3 ("a list of businesses you have
personally verified, imported by a script"). Agents and QA only ever run it
against throwaway SQLite files with made-up test rows.

The tool is `backend/scripts/import_businesses.py`. It is inside the Docker
image at `/app/looper/backend/scripts/import_businesses.py`.

What it does, in one breath:

- **Dry run by default.** It prints what it *would* insert, skip or reject and
  writes nothing. It writes only when you add `--apply`.
- Adds new rows only. It never changes or deletes an existing business. A row
  whose name + suburb already exists (ignoring accents, capitals and extra
  spaces, e.g. `Café Sol, Bondi` = `cafe sol, bondi`) is skipped, including
  businesses that came from HybridCard.
- New rows get `source = owner_verified`, `is_verified = false`,
  `is_active = true`. Search ranks them exactly like every other business
  (text match, reviews, distance). Being imported gives no boost.
- One transaction per run: with `--apply` either all good rows go in or none.
- Last line: `inserted N / skipped duplicate N / rejected N`.

---

## 1. Fill in the CSV

Copy `docs/templates/businesses.csv` (a header row only) and add one line per
business, **only businesses you have checked yourself**:

| Column | Required | Rule |
|---|---|---|
| name | yes | at most 200 characters |
| category | yes | e.g. `hairdresser`, `café`, `plumber` |
| suburb | yes | e.g. `Bondi` |
| address | no | |
| lat | yes | a number inside Australia, e.g. `-33.8908` (note the minus) |
| lng | yes | a number inside Australia, e.g. `151.2748` |
| phone | no | the business's public number, at most 20 characters |
| website | no | must start with `https://`, or leave it empty |
| description | no | |

Tip: in Google Maps, right-click the shop and click the numbers at the top to
copy `lat, lng`. Save as **CSV UTF-8**.

A bad line is rejected with its reason (for example
`REJECT  line 7: website must start with https:// (or be empty)`) and the rest
still import. Fix the line and run again: rows already imported are skipped.

## 2. Make a fresh backup first

Follow `docs/RUNBOOK-BACKUP-RESTORE.md` §2c ("Run it once by hand") so you
have a backup from **right now**. Write down its file name, for example
`/app/backups/looper-20261005T091500Z.db`. This is your undo button.

## 3. Dry run against a copy (on your Mac)

Copy that backup to a private folder on your Mac (it holds names and mobile
numbers, see the backup runbook §1), then from the repo root:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp ~/private/looper-20261005T091500Z.db /tmp/looper-copy.db
.venv/bin/python scripts/import_businesses.py \
  --csv ~/private/businesses.csv \
  --db sqlite:////tmp/looper-copy.db
```

(Four slashes after `sqlite:` = an absolute path.) Read every line. Expect
`WOULD INSERT`, `SKIP` and `REJECT` lines, then:

```
DRY RUN (nothing written; add --apply to write): would insert 12 / skipped duplicate 1 / rejected 0
```

Fix the CSV until the rejects are what you expect. Optional: add `--apply`
against the **copy** and try search locally
(`LOOPER_DB_URL=sqlite:////tmp/looper-copy.db LOOPER_PORT=8010 .venv/bin/python main.py`,
then `curl -s "http://localhost:8010/api/search?q=hairdresser"`).

## 4. Apply for real

In Coolify, open **looper-api → Terminal**. Put the CSV into the container
(paste your CSV between the two `EOF` lines):

```bash
cat > /tmp/businesses.csv <<'EOF'
name,category,suburb,address,lat,lng,phone,website,description
...your lines...
EOF
```

Dry run once more on the live file, then apply:

```bash
python /app/looper/backend/scripts/import_businesses.py --csv /tmp/businesses.csv --db sqlite:////app/data/looper.db
python /app/looper/backend/scripts/import_businesses.py --csv /tmp/businesses.csv --db sqlite:////app/data/looper.db --apply
rm /tmp/businesses.csv
```

The dry-run numbers and the `APPLIED:` numbers should match.

## 5. Check it

From your Mac (replace the word with one of your categories):

```bash
curl -s "https://api.localloop.ai/api/search?q=hairdresser" | python3 -m json.tool
```

Your businesses appear among the results, in the usual order (best text
match, then most reviews, then nearest).

## 6. Roll back

**Option A: restore the backup from step 2** (puts the whole database back
to that moment; anything written since is lost). Follow
`docs/RUNBOOK-BACKUP-RESTORE.md` §3 with the file name you wrote down.

**Option B: hide just the imported rows, keep everything else.** Nothing is
deleted; the rows are only switched off, so search stops showing them. In
**looper-api → Terminal**:

```bash
python -c "import sqlite3; c=sqlite3.connect('/app/data/looper.db'); n=c.execute(\"UPDATE businesses SET is_active=0 WHERE source='owner_verified'\").rowcount; c.commit(); print(n, 'rows hidden')"
```

To show them again, run the same line with `is_active=1`.

## 7. Remove this tool (rollback of the code)

Revert the PR that added it. It changed no schema and no route, so nothing
else needs undoing. Rows already imported stay (hide them with 6B if needed).

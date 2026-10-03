# Main CI recovery (#96)

An open `main is red` issue is actionable work: follow its Actions run link,
read the failing job log, and repair the cause through a normal small PR.
Do not weaken CI or patch the same failure inside several unrelated PRs.
The issue includes failed job IDs, the commit SHA, associated merged PRs (if
any), and the run link. Repeated failures comment on the existing issue. A
fully green main run comments `green again at <sha>` and closes it.

Only pushes to main run the monitor. PRs still use the same required `ci`
check. The script tests run in the backend job, before pytest. Only the
monitor has `issues: write`; its read scopes allow checkout, main-head and
merged-PR lookup. It uses the existing GITHUB_TOKEN, with no new secrets.
Job concurrency serializes issue updates; exact-title lookup scans all pages
and excludes PRs. Runs for superseded commits are ignored. Cancelled,
skipped or empty result sets do not establish recovery. The issue title is
reserved for this monitor: do not create or rename another issue to it.
API failures fail the reporting job rather than claiming success; check
that job if main is failing without an issue. A rerun can add another comment.

## Verify locally without contacting GitHub

From the repo root, using Python 3.12:

```bash
python3 -m unittest discover -s .github/scripts -p 'test_*.py' -v
```

Expected: 15 tests, `OK`. Then simulate failure (no token needed):

```bash
GITHUB_EVENT_NAME=push GITHUB_REF=refs/heads/main \
GITHUB_REPOSITORY=localloop-pro/looper GITHUB_SHA=example-sha \
GITHUB_SERVER_URL=https://github.com GITHUB_RUN_ID=123 \
JOB_RESULTS='{"backend":{"result":"failure"},"web":{"result":"success"}}' \
MAIN_RED_DRY_RUN=1 python3 .github/scripts/main_red.py
```

Expected JSON: `"action": "open"`, with `backend`, `example-sha`, and the
run URL in the body. To simulate recovery of an existing issue:

```bash
GITHUB_EVENT_NAME=push GITHUB_REF=refs/heads/main \
GITHUB_REPOSITORY=localloop-pro/looper GITHUB_SHA=example-sha \
GITHUB_SERVER_URL=https://github.com GITHUB_RUN_ID=124 \
JOB_RESULTS='{"backend":{"result":"success"},"web":{"result":"success"}}' \
MAIN_RED_DRY_RUN=1 MAIN_RED_EXISTING_ISSUE=42 \
python3 .github/scripts/main_red.py
```

Expected JSON: `"action": "close"`, `"issue": 42`, and
`green again at example-sha` in the body. Dry-run mode performs **no API calls**,
including reads. `MAIN_RED_MERGED_PRS` accepts a JSON array of PR fixtures
(`number`, `html_url`) to inspect the failure message with PR references.
Never run live mode locally just to test it.

## Rollback through a reviewed PR

Create a normal branch, remove only the `main-red` job from
`.github/workflows/ci.yml`, run the gates, and open a PR. Expected: all original
jobs and the required `ci` dependency list remain identical; no further
main-red issue writes occur after merge. The script, tests and documentation
can remain. Any already open incident issue then needs manual triage/closure.
No deployment, secrets or database change is needed.

# #88 — Test the production Docker image before Coolify

Host pytest does not exercise COPY paths, slim-image dependencies, the image's
CMD, HEALTHCHECK or mounted data directory. CI now builds from the repo root
with default build args (including scheduled-tool dependencies), then uses
`scripts/docker-smoke.sh` to check the actual image. The `ci` aggregate requires
`docker-smoke` to succeed, on both pull requests and main pushes.

The smoke uses an anonymous volume at `/app/data`, TypeDB disabled, no secrets,
and a random loopback-only port. It waits at most 60 seconds for the image's
own HEALTHCHECK, then checks health, search JSON shape, an empty review POST
returning 403, and absence of the search query in Docker logs. An EXIT trap
removes only the test container and its anonymous volume, including on failure.
The job has a four-minute timeout; it never publishes the image.

## Beginner verification (local only, Docker running)

From the repo root:

```bash
docker build -f backend/Dockerfile -t looper-api:ci .
bash scripts/docker-smoke.sh
```

Expect `Image HEALTHCHECK: healthy`, GET health/search `200 JSON`, POST reviews
`403 JSON`, `Docker logs: no request query string`, and `Docker smoke: PASS`.
The last line records elapsed seconds and exit 0. No real data is used.

Prove a broken CMD fails without changing the production Dockerfile:

```bash
docker build -t looper-api:ci-broken-cmd - <<'EOF'
FROM looper-api:ci
CMD ["python", "-c", "raise SystemExit(42)"]
EOF
bash scripts/docker-smoke.sh looper-api:ci-broken-cmd
```

Expect a nonzero exit and `Image failed to start` (or the 60-second deadline),
with container state/logs printed. This derivative image is local only.

## Validation and findings

- Base `70e5858`: backend collection failed because telemetry referenced `re`,
  `EMAIL_RE` and `AU_MOBILE_RE` without imports (introduced in PR #87). This PR
  restores those imports; existing tests then passed: 415 passed, 1 skipped.
- Web router/drift tests: 183 + 15 passed; Worker: 16 passed; bot typecheck,
  build and 47 unit tests passed. Compose configuration and Wrangler dry-run
  passed; local Wrangler dev preflight returned 200.
- Local Docker build and broken-CMD experiment are blocked: Docker Desktop's
  daemon is unreachable despite startup/restart attempts. Hosted Docker result
  and runtime must be recorded in the PR before acceptance.
- #86 and #76 were open at preparation time. No SOURCE_COMMIT build arg or
  commit assertion is included yet; preserve the Jarvis job if it lands before
  this PR and add the #86 check when its contract is merged.

## Follow-up: non-root runtime needs a separate volume plan

Do not add USER here. The existing Coolify volume is root-owned; switching UID
without an owner-approved backup, ownership migration and rollback can break
SQLite writes. Plan and test that separately with Bill. This smoke changes no
Dockerfile runtime behavior or production data.

## Rollback

In `.github/workflows/ci.yml`, remove the `docker-smoke` job and its entry from
the aggregate `ci.needs` list, then submit a PR. Keep all other required jobs
and the aggregate failure check. No Coolify action or data rollback is needed.

Reference: [Docker HEALTHCHECK](https://docs.docker.com/reference/dockerfile/#healthcheck)
and [GitHub job dependencies](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idneeds).

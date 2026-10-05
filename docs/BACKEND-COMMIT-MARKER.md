# Which commit is live on api.localloop.ai? (looper#86)

`GET /health` on the Looper API now says which git commit the running image
was built from:

```json
{"status": "healthy", "organization_identity": "/api/identity/health", "commit": "abc123def456"}
```

`commit` is the first 12 characters of the commit, or `""` when the image
does not know it. `/health` still answers 200 either way, so the Docker
healthcheck is unchanged.

**Who runs this:** the owner (Bill), once. Agents never touch Coolify.

## 1. Turn on the Coolify option (one time, 1 minute)

Coolify → the Looper API application → **Configuration → Advanced** →
tick **Include Source Commit in Build** → Save.

Coolify leaves this off by default so builds can reuse cached layers. The
`ARG SOURCE_COMMIT` sits near the end of `backend/Dockerfile`, so only the
last cheap layers rebuild per commit.

> Even with the option off, Coolify sets `SOURCE_COMMIT` inside the running
> container, and `/health` falls back to it. The option makes the commit part
> of the image itself, which is what you want to trust.

## 2. Redeploy

Press **Redeploy** on the same application (or merge something to `main`
if auto-deploy is on).

## 3. Compare live with main (30 seconds)

```bash
curl -s https://api.localloop.ai/health
git fetch origin && git rev-parse --short=12 origin/main
```

Expected (your commit will differ, the two values must match):

```text
{"status":"healthy","organization_identity":"/api/identity/health","commit":"782f7390c1ab"}
782f7390c1ab
```

- Same value → the latest `main` is live.
- Different value → an older build is running. Check the Coolify deploy log.
- `"commit":""` → the option is off, or the build ran outside Coolify.

The readiness check prints it too (GET only):

```bash
python3 scripts/loop_check.py --base-url https://api.localloop.ai
# PASS health: HTTP 200 (expected 200); commit 782f7390c1ab
```

It prints `commit unknown` when `/health` has no commit.

## Try it locally (no Docker needed)

```bash
cd backend
LOOPER_COMMIT=abc123def4567890 LOOPER_PORT=8010 .venv/bin/python main.py
# other terminal:
curl -s localhost:8010/health
# {"status":"healthy","organization_identity":"/api/identity/health","commit":"abc123def456"}
```

With Docker:

```bash
docker build -f backend/Dockerfile --build-arg SOURCE_COMMIT=abc123def4567890 -t looper-api .
docker run --rm -p 8010:8000 looper-api
curl -s localhost:8010/health   # ... "commit":"abc123def456"
```

Build without `--build-arg` and the same curl shows `"commit":""`.

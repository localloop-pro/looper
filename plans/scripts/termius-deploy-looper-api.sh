#!/usr/bin/env bash
# Paste into Termius as root@167.86.79.151 — durable looper-api origin for CF Worker.
# Does NOT touch Coolify web UI. Publishes host :8001 for Worker ORIGIN.
set -euo pipefail

INGEST_SECRET="${HYBRIDCARD_INGEST_SECRET:-}"
if [[ -z "$INGEST_SECRET" ]]; then
  echo "Set HYBRIDCARD_INGEST_SECRET first, e.g.:"
  echo "  export HYBRIDCARD_INGEST_SECRET='<from secrets/bridge-online.env>'"
  exit 1
fi

WORKDIR=/opt/looper
mkdir -p "$WORKDIR/data"
cd /opt

if [[ ! -d looper/.git ]]; then
  git clone --depth 1 https://github.com/localloop-pro/looper.git
else
  cd looper && git fetch --depth 1 origin main && git reset --hard origin/main && cd /opt
fi

cd /opt/looper
docker build -f backend/Dockerfile -t looper-api:latest .

docker rm -f looper-api 2>/dev/null || true
docker run -d --name looper-api --restart unless-stopped \
  -p 8001:8000 \
  -v /opt/looper-data:/app/data \
  -e HYBRIDCARD_INGEST_SECRET="$INGEST_SECRET" \
  -e HYBRIDCARD_KEY_IDS=hc-1 \
  looper-api:latest

sleep 2
curl -fsS http://127.0.0.1:8001/health
echo
echo "ORIGIN for CF Worker: http://167.86.79.151:8001"
echo "Then from Mac: cd workers/looper-api-proxy && npx wrangler deploy"

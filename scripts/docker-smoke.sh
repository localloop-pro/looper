#!/usr/bin/env bash
# Runner-side smoke test; build the production image from the repo root first.
set -euo pipefail

image="${1:-looper-api:ci}"
container=""
started=$SECONDS
cleanup() {
  result=$?
  trap - EXIT
  if [ -n "$container" ]; then
    if [ "$result" -ne 0 ]; then
      docker inspect --format '{{json .State}}' "$container" >&2 || true
      docker logs "$container" >&2 || true
    fi
    # -v removes only this container's anonymous, throwaway data volume.
    docker rm -fv "$container" >/dev/null || true
  fi
  echo "Docker smoke elapsed: $((SECONDS - started))s (exit $result)"
  exit "$result"
}
trap cleanup EXIT

# Loopback-only random port avoids local collisions; no host env or data mounted.
# Do not override CMD or HEALTHCHECK: those are part of the production contract.
container=$(docker create -p 127.0.0.1::8000 -v /app/data \
  -e TYPEDB_ENABLED=false "$image")
docker start "$container" >/dev/null
deadline=$((SECONDS + 60))
while true; do
  state=$(docker inspect --format '{{.State.Status}}' "$container")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container")
  if [ "$state" != running ] || [ "$health" = missing ] || [ "$health" = unhealthy ]; then
    echo "Image failed to start or has no passing HEALTHCHECK: $state / $health" >&2
    exit 1
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo 'Image HEALTHCHECK did not become healthy within 60s' >&2
    exit 1
  fi
  if [ "$health" = healthy ]; then break; fi
  sleep 1
done
echo 'Image HEALTHCHECK: healthy'

address=$(docker port "$container" 8000/tcp)
python3 - "http://$address" <<'PY'
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = sys.argv[1]

def probe(path, expected, data=None):
    request = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        assert response.code == expected, f"{path}: expected {expected}, got {response.code}"
        assert response.headers.get_content_type() == "application/json", f"{path}: not JSON"
        payload = json.load(response)
    print(f"{request.method} {path.split('?')[0]}: {expected} JSON")
    return payload

health = probe("/health", 200)
assert health["status"] == "healthy", health
search = probe("/api/search?q=cafe&lat=-33.8908&lng=151.2748", 200)
assert isinstance(search, dict), search
assert search["query"] == "cafe", search
assert isinstance(search["results"], list), search
assert isinstance(search["message"], str), search
assert type(search["total_results"]) is int and search["total_results"] >= 0, search
# Empty body proves the guard runs before validation and cannot create a review.
probe("/api/reviews", 403, b"{}")
PY

# Read logs on the runner, including stderr. Fail if the search query leaked in
# either an access line or any other record; structured path-only traces are OK.
logs=$(docker logs "$container" 2>&1)
if printf '%s\n' "$logs" | grep -Eq '/api/search\?|q=cafe|lat=-33\.8908|lng=151\.2748'; then
  echo 'Request query string leaked into Docker logs' >&2
  exit 1
fi
echo 'Docker logs: no request query string'
echo 'Docker smoke: PASS'

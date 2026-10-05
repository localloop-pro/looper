#!/usr/bin/env bash
# Run from any directory; only the server started here is stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m http.server 8088 --bind 127.0.0.1 &
server_pid=$!
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

ready=false
for attempt in {1..30}; do
  sleep 0.2
  # A pre-existing listener must not let a failed server startup pass.
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Jarvis smoke server exited before becoming ready" >&2
    exit 1
  fi
  if curl --fail --silent --max-time 1 http://127.0.0.1:8088/tests/jarvis-harness.html >/dev/null; then
    ready=true
    break
  fi
done
if [ "$ready" != true ]; then
  echo "Jarvis smoke server did not answer on port 8088" >&2
  exit 1
fi
node tests/jarvis-smoke.playwright.js

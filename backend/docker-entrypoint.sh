#!/usr/bin/env sh
# Production uvicorn launcher (Coolify / Docker). Keeps proxy-header trust off
# the public internet: only RFC1918 ranges + loopback by default; override with
# LOOPER_FORWARDED_ALLOW_IPS (comma-separated IPs/CIDRs, same as uvicorn).
set -eu

allow_ips="${LOOPER_FORWARDED_ALLOW_IPS:-127.0.0.1,172.16.0.0/12,10.0.0.0/8,192.168.0.0/16}"
port="${LOOPER_PORT:-8000}"

exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "$port" \
  --no-access-log \
  --proxy-headers \
  --forwarded-allow-ips "$allow_ips"
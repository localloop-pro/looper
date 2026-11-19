# Narrow uvicorn forwarded-header trust (post PR A front door)

Production previously ran `--forwarded-allow-ips=*`, which lets any client
spoof `X-Forwarded-Host` / `X-Forwarded-Proto` on paths that reach uvicorn
without Traefik. The image now starts via `backend/docker-entrypoint.sh` with
`LOOPER_FORWARDED_ALLOW_IPS` (default: loopback + RFC1918 CIDRs). Coolify
operators can tighten to Traefik’s container IP if desired; do not set `*`.
# PR A — api.localloop.ai public front door (2026-11-17)

The FastAPI app keeps a **dark** public root until `LOOPER_FRONTDOOR_LIVE=1`.
Dark behaviour matches today's fixed JSON on `GET /` (key order
`name, version, status, docs, organization_identity`). Live enables Accept
negotiation on `/` (HTML only when `text/html` beats JSON on q-values), plus
`/reference`, `/robots.txt`, `/llms.txt`, `/sitemap.xml`, and a 301 from
`/docs` → `/reference`. `/api/*` is never content-negotiated.

Always on (not gated): `redirect_slashes=False` so `/docs/` and `/health/`
never 307 to the internal `http://…sslip.io` host; uvicorn `--proxy-headers`
with a narrowed `LOOPER_FORWARDED_ALLOW_IPS` (see `docker-entrypoint.sh`) so
absolute redirects trust the worker's `X-Forwarded-Host` / `X-Forwarded-Proto`
only from the reverse proxy; explicit `GET`+`HEAD`
on `/`, `/health`, and `/reference`.

Owner rollout (not agent actions): deploy image first with the flag still
`0`; set worker `ORIGIN_KEY` before server `LOOPER_ORIGIN_KEY`; only then
flip `LOOPER_FRONTDOOR_LIVE=1`.

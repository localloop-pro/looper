# F4.3 sanctioned pending-pin cockpit — Looper evidence

Date: 2026-08-12

## Contract consumed

Canonical provider spec (llx11):
`.governance/specs/SPEC-055-looper-pending-pin-read-api.md`

```text
GET ${LOCALLOOP_GATEWAY_URL}/api/bot/map/pins
  ?source=hybridcard
  &status=pending_review
  &page=1
  &limit=20
Authorization: Bearer ${LOOPER_BOT_READ_TOKEN}
```

LocalLoop provider merge:

- main merge via PR #80: `d77ccf8659638f71ee39f813691ecd597d1aa0d3`
- feature PR #79 squash on develop: `7043938`
- core commit: `71c3052`
- fail-closed outage hardening: `af31947`
- reported evidence: focused 14/14, full unit 129/129, smoke,
  contract/secret scan, build, and Wrangler dry-run green
- merge checks: Install+Secret Scan+Lint, Unit/Integration, Playwright E2E,
  and `ci-required` all green; issue #78 closed
- **not live/activated yet** — no production pending-pin request is claimed

## Looper implementation

- `looper-bot/electron/localloop-gateway-tools.cjs`
- `localloop_pending_pins` tool spec + execution route in `electron/main.cjs`
- `localloop_gateway_health` tool (public read-only health)
- token remains in Electron main; preload exposes no environment or token
- no Supabase client/query exists in this path
- fixed source/status filters; page 1..10000; limit 1..50
- strict response/pagination validation and exact 21-field projection
- unsafe/non-HybridCard card URLs, Markdown/HTML control text, and unknown/raw
  fields removed or escaped; every pin must retain the fixed source/status
- HTTPS required except loopback development; credentials/path/query/fragment
  bases and redirects rejected to prevent bearer-token exfiltration
- gateway's redacted error codes mapped without echoing response details
- a 200 artifact states the gateway audit guarantee; all audit failures return
  no pins or table

## Verification

```bash
cd looper-bot
npm test
# 15 passed

npm run typecheck
# passed

npm run build
# passed (only the existing Vite chunk-size warning)

node --check electron/main.cjs
node --check electron/localloop-gateway-tools.cjs
# passed
```

Public gateway health through the new client:

```json
{"ok":true,"service":"looper-gateway","version":"0.1.0","mode":"connector-first","error":null}
```

## Remaining acceptance gate

1. Bill approves/applies `db/migrations/looper_gateway_audit_log.sql` and
   deploys the merged Worker route.
2. Owner configures the same random 32+ byte `LOOPER_BOT_READ_TOKEN` in the
   Worker secret store and Looper `.env.local` (never browser config).
3. Invoke `localloop_pending_pins` against the live route and record a 200 plus
   corresponding `pin_pending_list_read` audit row.
4. Bill asks, “any card deals waiting for approval?” and verifies the spoken
   exact count + table artifact.

Until all four pass, F4.3 remains unchecked.

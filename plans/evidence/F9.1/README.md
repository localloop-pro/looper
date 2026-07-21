# F9.1 / online bridge smoke — 2026-07-21

## Public health
{"status":"healthy"}

## Architecture
- Route: Cloudflare Worker `looper-api` → ORIGIN (cloudflared quick tunnel → local :8001)
- Coolify UI login blocked (password in secrets/looper-coolify.env rejected); Railway Metal builder failed
- Gateway: `looper.localloop.ai` Worker with BRIDGE_EVENTS_KV + LOCALLOOP_BRIDGE_SECRET

## Signed deal ingest (api.localloop.ai)
200 {"ok":true,"duplicate":false}

## Bridge pin (looper.localloop.ai/api/bridge/pin)
{
  "ok": true,
  "duplicate": false,
  "eventId": "86f44ade-e827-46a0-a831-07b89228dd53",
  "active": true,
  "created": true,
  "moderation_status": "pending_review",
  "pin": { "id": "27808ad0-5cbb-4dce-8b41-bf43493b7da2" },
  "action": "inserted",
  "idempotency": "kv"
}
HTTP:201

## Pin label
Online Smoke Cafe (TEST) — approve in Supabase or delete after review

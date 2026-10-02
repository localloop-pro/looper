# E6 release gate — tracing, SLOs, rollout and rollback (Looper side)

Issue: looper#9. This file is the gate every E2–E5 change must pass before the
owner approves a production rollout. It covers what Looper can own and prove
today. Items that live in LocalLoop or HybridCard are marked **(other repo)**
and point at their issue.

Status on 2026-10-02: E1 (localloop.pro-main#100) has no accepted ADR, and
E2–E5 are still open. The thresholds below are **provisional** until E1 sets
the real numbers. Nothing here is deployed.

---

## 1. One correlation convention (no PII)

There is one key per hop type:

| Hop | Key | Who sets it | Rule |
|---|---|---|---|
| Browser → Worker → Looper API (HTTP) | `X-Request-ID` | the first hop that has none | opaque, 8–128 chars of `[A-Za-z0-9._:-]`, at least one letter |
| HybridCard → Looper / LocalLoop bridge | payload `eventId` | HybridCard outbox | already in the frozen BRIDGE-CONTRACT-v1 payload; no new header |
| Looper bridge receipt → its HTTP request | `rid` field on the `bridge` record | Looper | joins the two records |

Rules, enforced in `backend/services/correlation.py`:

- **Validate and keep, or replace.** A safe inbound id is kept. Anything else
  is replaced with a fresh uuid4 hex. "Anything else" includes a phone number
  (digits only), an email, whitespace, markup, `Bearer …`, or the wrong length.
  The replacement is written back into the request, so every inner layer sees
  the same id, and it is echoed on the response.
- **Allowlisted fields only.** The `http` record has exactly `ts, kind, rid,
  method, route, status, dur_ms, cache`. `route` is the template
  (`/api/users/{user_id}`), never the raw path or the query string. Voice
  queries are free text and can contain dictated contact details.
- **Never logged:** the client IP, `User-Agent`, cookies, the `Authorization`
  header, `X-HC-Signature`, request or response bodies, business names, card
  ids and card URLs.
- **The `bridge` record** has exactly `ts, kind, receiver, rid, event_id,
  event_type, outcome, delivery_age_s`.
  - `outcome` is one of `processed`, `duplicate`, `stale_skipped`,
    `unauthorized`, `invalid_payload` or `too_large`.
  - `event_id` is logged only when it is an opaque token. It is always `null`
    for rejected deliveries, so an unauthenticated caller cannot write
    arbitrary text into the log.
  - `delivery_age_s` is the receive time minus the payload `updated_at`. It
    includes every outbox retry. `X-HC-Timestamp` can't be used, because the
    sender re-signs each retry with a fresh timestamp.
- **Bounded retention.** Each record is one fixed-shape JSON line on stderr
  (under 512 bytes). Looper keeps nothing in memory or on disk. Retention is
  the log sink's rotation (Coolify/Docker), and no payload is ever retained by
  tracing.
- **Kill switch:** `LOOPER_TRACE_LOG=off` stops the lines. The header echo
  stays.

What the other hops must do to join the chain:

- **Worker `workers/looper-api-proxy`** already forwards all request headers,
  so a caller's `X-Request-ID` reaches Looper. Optional upgrade (devops lane):
  when the header is missing, set it from `cf-ray`. That is opaque and lets
  Cloudflare logs join Looper logs.
- **LocalLoop map / gateway (other repo, localloop.pro-main#101/#102):** send
  `X-Request-ID` on browser calls to `looperApi` (a `crypto.randomUUID()` per
  voice turn), and validate inbound ids with the same rule.
- **HybridCard outbox (other repo, hybridcard-v2#62):** log `eventId`,
  `attempts`, `status` and `lastError` per drain. Never log the payload. No
  header or payload change is needed (the contract stays frozen).

## 2. SLOs and how to compute them

Thresholds live in `tools/slo_thresholds.json`. They are provisional and
measured at the FastAPI origin.

| SLO | Threshold | Source |
|---|---|---|
| Availability (non-5xx share) | ≥ 99.5 % | `http` records |
| `/api/search`, `/api/discover`, `/api/businesses` p95 | ≤ 300 ms, with ≥ 20 samples each | `http` records |
| Bridge delivery age p95 | ≤ 900 s | `bridge` records with `processed` |
| Bridge duplicate ratio (retries/replays) | ≤ 0.25 | `bridge` records |
| Bridge `unauthorized` / `invalid_payload` / `too_large` | 0 | `bridge` records |
| Gateway 5xx/502 | (other repo) | Cloudflare Worker analytics |
| Dead letters | 0 new in 7 days | HybridCard outbox, below |

**Report and gate:**

```bash
python3 tools/slo_report.py report trace.log --out candidate.json   # exit 1 = an SLO is breached
python3 tools/slo_report.py compare baseline.json candidate.json   # exit 1 = no release
```

`trace.log` can be a raw `docker logs` or Coolify log export, because other
lines are skipped. Too few samples counts as a failure, never a pass.

**Sender-side numbers (owner runs these read-only in HybridCard; Looper never
connects to Mongo):**

```js
db.v2_outbox.countDocuments({ status: "dead" })                       // dead letters
db.v2_outbox.countDocuments({ status: "failed" })                     // waiting to retry
db.v2_outbox.aggregate([{ $group: { _id: "$status", attempts: { $avg: "$attempts" } } }])
```

The sender dead-letters after 6 attempts with a 30 s × 2ⁿ backoff (≈ 31 min
end to end). That is why 900 s is the provisional delivery-age p95.

## 3. Release gate (what "ready for the owner" means)

A release goes to the owner only when all of these are true:

1. The full backend suite is green:
   `cd backend && .venv/bin/python -m pytest -q`.
2. `tools/e6_nonprod_check.py` passes all checks against a throwaway
   non-prod target. That covers load, contract and adversarial.
3. `slo_report.py report` passes on a clean window. Run the load and contract
   phases only, because the adversarial phase deliberately plants 401 and 413
   deliveries.
4. `slo_report.py compare` passes against the E1 baseline:
   - at least 10 % p95 improvement on one target route;
   - no target route more than 5 % slower;
   - no drop in availability;
   - no rise in bridge `unauthorized` or `invalid_payload`.
5. The router suite passes (`node web/tests/voice-command-router.test.js`), and
   the anti-bias tests show the ranking order is unchanged.
6. The rollback steps (section 5) were run once on the non-prod target.
7. The non-prod evidence is attached to the PR, and the owner signs off on
   the issue. **Nobody but the owner flips production.**

## 4. Feature flags and canary

Every E-series change ships dark behind an env flag with a safe default:

| Flag | Default | Effect | Owner of change |
|---|---|---|---|
| `LOOPER_TRACE_LOG` | `on` | trace lines on stderr (no data written) | this PR |
| `LOOPER_READ_CACHE_TTL_S` / `_STALE_S` | `0` (off) | read cache | looper#8 (PR #16, merged dark) |
| `LOOPER_READ_RATE_LIMIT_PER_MIN` | `0` (off) | per-client read limit | looper#8 (PR #16, merged dark) |
| `TYPEDB_ENABLED` | `false` | graph brain, falls back to SQLite | frozen (BLIND-SPOTS §6) |

**Canary:** Looper runs as one Coolify app, so a canary is a time-boxed flag
flip, not a traffic split:

1. In an owner-approved change window, flip one flag.
2. Watch for 30 minutes: run `slo_report.py report` on the window's logs.
3. Then either keep the flag on for 24 h, or roll back (section 5).

A percentage split belongs at the Worker (devops lane, other issue).

## 5. Rollback (no data repair, ever)

| Change | Rollback | Data repair |
|---|---|---|
| Tracing (this PR) | set `LOOPER_TRACE_LOG=off` and restart, or `git revert` and redeploy | none: tracing writes no rows |
| Read cache / rate limit (PR #16) | set the flags to `0` and restart | none: in-process only |
| Any backend release | Coolify: redeploy the previous commit | none: bridge receipts are idempotent on `eventId`, and the sender retries every non-2xx, so events missed during a bad deploy re-arrive |
| Bridge receiver regression | revert. Do **not** delete `bridge_events` rows; replays become `duplicate` | none |

**Tested on 2026-10-02 (local, throwaway DB):** with `LOOPER_TRACE_LOG=off`
the server wrote 0 trace lines, still returned `X-Request-ID`, and the
contract checks passed.

## 6. Incident playbooks

| Symptom (from `slo_report` or a user) | First check | Action |
|---|---|---|
| "Looper brain is offline" on the map | `.SEED/gotchas.md` entry 1: CORS + `LOOPER_API_URL` | fix config; no code rollback |
| 5xx spike / availability < 99.5 % | `http` records grouped by `route`; find the first bad `rid` | roll back the last deploy (section 5) |
| p95 over threshold | `dur_ms` by route; `cache` column if #16 is on | turn the newest flag off |
| Bridge `unauthorized` > 0 | key drift: `X-HC-Key-Id` / secret mismatch after a rotation | owner re-aligns the secret (hot zone: secrets). Events retry by themselves |
| Bridge delivery age p95 high, or dead letters | sender drain cadence; HybridCard outbox query (section 2) | owner re-drains (`POST /api/internal/bridge/drain` on HybridCard). Receivers are replay-safe |
| PII found in any log | which field; `grep` the export | `LOOPER_TRACE_LOG=off`, open an issue, purge the sink. Never copy the line into the issue |

## 7. Security review (Looper origin)

| Area | Status | Evidence / gap |
|---|---|---|
| Logging leakage | ✅ allowlist records, unsafe ids replaced | `tests/test_correlation_trace.py` |
| Replay | ✅ idempotent on `eventId`; out-of-order retries skipped; ±5 min HMAC window | `test_bridge_hmac.py`, `test_ingest_*`, non-prod check |
| Authorization (bridge) | ✅ HMAC over the raw body, constant-time compare, 401/413 | non-prod check: tampered, expired, unknown key, wrong secret, unsigned → 401 |
| CORS | ✅ exact allowlist; a foreign origin gets no grant; preflight from a foreign origin is 400 | non-prod check + tests |
| SSRF / open proxy | ✅ the origin never fetches caller-supplied URLs; proxy-shaped paths are 404 | non-prod check. Worker: forwards only to its fixed `ORIGIN` |
| Cache isolation | ✅ at the origin, shipped dark (PR #16): key = ranking params only, no identity; `Authorization` bypasses | `test_edge_read_boundary.py`. A future Worker cache must key on `Origin` (`docs/EDGE-READ-BOUNDARY.md` §5) |
| Rate limits | ⏳ built, dark (PR #16) | do not enable until the origin is locked to Cloudflare (`docs/EDGE-READ-BOUNDARY.md`). 429s are traced: `test_one_id_through_read_boundary_and_hits_are_traced` |
| Authorization (public writes) | ❌ known gap | `POST /api/reviews` is open (BLIND-SPOTS §3.6). Hot zone (auth): owner decision needed |
| `/api/ingest/status` | ⚠️ public | event ids, types and counts only; no payload bodies (asserted by the non-prod check) |

## 8. Evidence and what is still open

The local non-prod evidence is in the PR for looper#9. Still open, and outside
this repo or owner-gated:

- [ ] Cross-repo browser E2E (map → Worker → Looper → card link) against a
  staging target. This needs localloop.pro-main#101/#102 and a non-prod
  HybridCard.
- [ ] Replace the provisional thresholds with the E1 ADR numbers.
- [ ] LocalLoop and HybridCard adopt section 1 (their E2/E3/E5 issues).
- [ ] Owner sign-off on production rollout.

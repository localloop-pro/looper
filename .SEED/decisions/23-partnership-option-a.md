# #23 — Partnership events: Option A, stop sending; no Looper receiver (2026-10-04)

**Decided by the owner:** https://github.com/localloop-pro/looper/issues/23#issuecomment-5978692500
(OWNER account, 2026-10-04T09:52:08Z): "OK (a): HybridCard should stop sending
partnership events to Looper until a receiver exists. Keep the existing 422
guard; do not replay the dead letters."

- HybridCard stops sending `partnership.upserted` / `partnership.removed` to
  Looper (`outbox.ts:209-230` `enqueuePartnershipEvents`). That change is in
  hybridcard-v2 (#104 there), not in this repo. **Done:** hybridcard-v2 PR #257
  "stop unsupported partnership deliveries" merged 2026-10-06 and #104 is closed.
- Looper builds no partnership receiver, adds no `card_partnerships` table and
  does not loosen `HybridCardCardPayload`. BRIDGE-CONTRACT-v1 is unchanged.
- The guard stays: `POST /api/ingest/hybridcard-card` answers 422 to a
  partnership payload and writes nothing
  (`backend/tests/test_ingest_partnership_mismatch.py`). Never remove it while
  HybridCard can still send these events.
- Never replay the `v2_outbox` partnership dead letters, now or later.
- A receiver later needs a new owner decision on a new issue (it would be a
  BRIDGE-CONTRACT-v1 + schema hot zone). Options (b) receiver and (c) TypeDB
  only (BLIND-SPOTS §6 freeze) were not chosen.

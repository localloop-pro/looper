# #23 — No partnership receiver until the owner picks (a), (b) or (c) (2026-10-02)

- HybridCard sends `partnership.upserted` / `partnership.removed` to
  `POST /api/ingest/hybridcard-card`, which answers 422 and writes nothing.
  `tests/test_ingest_partnership_mismatch.py` pins that, so the eventIds stay
  unused and a future receiver can still accept a replay.
- Choosing between (a) stop sending, (b) new `/api/ingest/hybridcard-partnership`
  receiver (new `card_partnerships` table = schema change) and (c) TypeDB only
  (BLIND-SPOTS §6 freeze) is a BRIDGE-CONTRACT-v1 hot-zone decision. Agents
  don't build a receiver, loosen `HybridCardCardPayload`, or replay the
  `v2_outbox` dead letters until the owner's OK is recorded on looper#23 or
  hybridcard-v2#104. If (a), the guard test stays and #23 closes with no code.

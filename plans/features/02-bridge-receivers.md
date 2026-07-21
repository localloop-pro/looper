# 02 — Phase 1 — The Bridge: receivers live (HybridCard → map + brain)

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [x] **F1.1** — Looper deal-ingest receiver (`POST /api/ingest/hybridcard-deal`)
- [x] **F1.2** — Looper card-ingest receiver (`POST /api/ingest/hybridcard-card`)
- [x] **F1.3** — LocalLoop `/pin` receiver (looper-gateway worker)
- [x] **F1.4** — HybridCard pins render on the Explore map
- [x] **F1.5** — End-to-end bridge dry run (staging) — online upsert+pin draft green 2026-07-21 (`plans/evidence/F9.1/`); Bill still approves/removes TEST pin in Supabase

---


---

**F1.1 — Looper deal-ingest receiver (`POST /api/ingest/hybridcard-deal`)**

- **What:** The FastAPI receiver for **LooperIngestPayload** (frozen §3b of
  BRIDGE-CONTRACT-v1). This is the single most important missing piece —
  HybridCard is already trying to send to it.
- **Files (new):** `backend/routes/ingest.py`,
  `backend/services/bridge_hmac.py`, `backend/models.py` (add two tables),
  `backend/tests/test_ingest.py`.
- **Steps:**
  1. `bridge_hmac.py`: `verify(raw_body: bytes, headers) -> key_id`.
     Recompute `HMAC_SHA256(secret, f"{ts}.{raw}")` where secret is looked up
     by `X-HC-Key-Id` from env `HYBRIDCARD_INGEST_SECRET` (support a dict for
     future key rotation, default id `hc-1`). Constant-time compare
     (`hmac.compare_digest`). Reject: unknown key id, non-numeric ts,
     `abs(now_ms - ts) > 300_000`. IMPORTANT: read the RAW request body
     before Pydantic parsing (`await request.body()`).
  2. New models: `bridge_events` (`event_id` UNIQUE, `target`, `payload`
     JSON, `received_at`, `status`) and `deals` (`deal_id` UNIQUE,
     `business_id` FK, `title`, `short_description`, `category`, `pin_type`,
     `sub_type`, `discount_size`, `lat`, `lng`, `hours`, `public_card_url`,
     `active`, `updated_at`).
  3. Route logic (idempotent): if `event_id` already in `bridge_events` →
     return `200 {"ok":true,"duplicate":true}`. Else upsert `businesses`
     keyed on **`hybrid_card_id`** (create with `source="hybrid_card"`,
     update name/category/lat/lng), upsert `deals` on `deal_id`, set
     `active` from payload (`deal.removed` ⇒ `active=false`, never delete),
     record event, return 200 ONLY after commit.
  4. Never use `discount_size` or `source` in search ranking
     (`routes/search.py` untouched — add a code comment + test asserting
     ranking inputs).
- **Acceptance (must all pass in `pytest`):**
  - valid signed payload → 200, business + deal rows exist;
  - same `eventId` replayed → 200, still exactly one row each;
  - bad signature / stale timestamp / unknown key id → 401, no rows;
  - `deal.removed` → `deals.active=false`, row NOT deleted;
  - a business search never orders by discount (anti-bias test).
  - Manual: `python tests/send_signed_event.py` helper script (write it)
    posts a sample payload with a locally generated signature.
- **Depends:** F0.3, F0.4.

---

**F1.2 — Looper card-ingest receiver (`POST /api/ingest/hybridcard-card`)**

- **What:** Receiver for the T2 card-lifecycle payloads
  (`event_kind:'card'`, `card.upserted` / `card.removed`) so every published
  card (not just deals) becomes a LOOPER business. HybridCard's env for this
  is `LOOPER_CARD_INGEST_URL`.
- **Steps:** same HMAC module; upsert `businesses` on `hybrid_card_id` with
  `name`, `category` (mapped via contract §5), `lat/lng`, `website =
  public_card_url`; `active:false` ⇒ `is_verified` stays, business flagged
  inactive (add `is_active` column).
- **Acceptance:** same idempotency/HMAC matrix as F1.1; card unpublish
  deactivates the business and its deals stop appearing in `/api/search`.
- **Depends:** F1.1.

---

**F1.3 — LocalLoop `/pin` receiver (looper-gateway worker)**

- **What:** Receiver for **MarkerPayload** (frozen §3a) that turns card deals
  into *draft* Supabase `pin` rows awaiting approval. Lives in the existing
  Cloudflare Worker (Phase-18A decision: `localloop.pro-main` owns it).
  Endpoint: `POST /api/bridge/pin` — and set HybridCard's
  `LOCALLOOP_BRIDGE_URL` so `/pin` resolves here (e.g.
  `https://looper.localloop.ai/api/bridge` → worker route appends `/pin`).
- **Files:** `workers/looper-gateway/src/bridge-pin.mjs` (new),
  `src/index.mjs` (route), `wrangler.jsonc` (new secret
  `LOCALLOOP_BRIDGE_SECRET`), `tests/looper-gateway-bridge-pin.unit.js`.
- **Steps:**
  1. HMAC verify exactly as F1.1 (raw body, `X-HC-*`, ±5 min, constant-time
     — reuse the worker's existing timing-safe compare helper).
  2. Map payload → `pin` row: `category` from contract category →
     pin_category (**mapping table:** café→`Food`, accommodation→
     `Accommodation`, event→`Events`, everything else→`Offers`),
     `tier: 'premium'` (cards are paying businesses),
     `coordinates: SRID=4326;POINT(lng lat)`,
     `payload: { source: "hybridcard", moderation_status: "pending_review",
     event_id, deal_id, hybrid_card_id, slug, business_name, logo_url,
     marker_size, discount_pct, title, short_description, claim_url,
     vip_count, rating, hours, expires_at }`.
  3. Idempotent upsert: SELECT by `payload->>deal_id`; update if exists
     (including `active:false` ⇒ set `payload.moderation_status='removed'`
     and expire the pin), else INSERT via service role (reuse the PostgREST
     pattern from `pin-write.mjs`).
  4. Return 2xx only on durable success (the sender retries all non-2xx).
  5. Do NOT bypass moderation: drafts stay invisible until F5.2 approval.
- **Acceptance:** unit tests (mock fetch to PostgREST) for HMAC matrix +
  idempotent upsert + category mapping + deactivate; `wrangler dev` manual
  signed POST creates a pending pin visible in Supabase table editor and
  NOT on the public map.
- **Depends:** F0.3 (secret), F1.1 (shared HMAC vector fixtures — reuse the
  same test vectors so both receivers agree byte-for-byte).

---

**F1.4 — HybridCard pins render on the Explore map**

- **What:** Approved hybridcard pins show as logo markers sized by
  `marker_size`, with a popup: business name, title, discount, ⭐ rating,
  VIP count, and **"View card →" linking `claimUrl`**
  (`https://<slug>.hybridcard.ai`).
- **Files:** `assets/js/hybridcard-markers.js` (new, follows the
  `simple-news-markers.js` wrapper pattern), one `<script>` include +
  `_redirects` check in `index.html` (surgical), small CSS block.
- **Steps:** query the `local_loop_business_layer`-style path: select `pin`
  where `payload->>source = 'hybridcard'` AND `payload->>moderation_status
  IN ('approved','published')` AND active; render Mapbox markers (logo image
  with fallback dot; size map small=28px / medium=38px / large=48px /
  supersized=64px); popup template; refresh on `map.moveend` within
  viewport bounds.
- **Acceptance:** seed one approved test pin → marker renders at correct
  size; popup "View card →" opens the card subdomain in a new tab;
  pending/removed pins never render; Lighthouse perf unchanged (>90).
- **Depends:** F1.3.

---

**F1.5 — End-to-end bridge dry run (staging)**

- **What:** Prove the whole pipe: new-card outbox → drain cron → both
  receivers → approval → map pin, on staging URLs.
- **Steps:** deploy F0.4 + F1.x to staging (Phase 9 gives the full recipe;
  a minimal staging is enough here); set `LOOPER_INGEST_URL` +
  `LOCALLOOP_BRIDGE_URL` + secrets in the new-card staging env; create a
  test deal in HybridCard; run drain
  (`curl -X POST …/api/internal/bridge/drain -H "x-cron-secret: $CRON_SECRET"`);
  approve the draft pin; see the marker.
- **Acceptance:** outbox event goes `pending→sent` (not `dead`); looper
  `businesses.hybrid_card_id` populated; pin approved → visible in <1 min;
  `deal.removed` → marker disappears + looper deal inactive. Record evidence
  screenshots in `plans/evidence/F1.5/` (agent-collab style).
- **Depends:** F1.1–F1.4.

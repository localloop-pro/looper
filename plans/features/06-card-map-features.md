# 06 — Phase 5 — Card ↔ map business features

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F5.1** — Draft-pin approval UI (moderation queue)
- [ ] **F5.2** — Claimed-business popups link to cards ("View card →")
- [ ] **F5.3** — "Get your Hybrid Card" funnel from the map
- [ ] **F5.4** — Archetype assist surfaced to owners

---


---

**F5.1 — Draft-pin approval UI (moderation queue)**

- **What:** An admin-only "Pending card pins" panel (extend the existing
  `dashboard.html`) listing pins where `payload->>source='hybridcard'` AND
  `moderation_status='pending_review'`: business, title, discount, preview
  location; Approve / Reject buttons.
  **Writes go through the worker, never the browser with service keys:**
  new endpoint `POST /api/admin/pins/moderate` in looper-gateway —
  Supabase-JWT-verified (reuse `pin-write.mjs` verifier) + user id must be
  in new worker var `ADMIN_USER_IDS`; body
  `{pin_id, decision: "approved"|"rejected"}`; sets
  `payload.moderation_status` accordingly; audit-logs the action.
- **Acceptance:** non-admin JWT → 403; approve flips the pin to visible on
  the map (F1.4 query picks it up) within one refresh; reject hides it
  permanently; every decision has an audit row.
- **Depends:** F1.3, F1.4.

---

**F5.2 — Claimed-business popups link to cards ("View card →")**

- **What:** Complete the agent-collab Phase C flow: approved claim pins
  (Business Truth Layer) whose payload carries `business_slug` (or a
  hybridcard match by name) show "View card →" → `/hybridcard/{slug}` page
  (hydrates from the moderated pin row; `_redirects` rule
  `/hybridcard/* /hybridcard.html 200` must exist), and card-side
  `claimUrl` pins (F1.4) link out to `https://<slug>.hybridcard.ai`.
- **Acceptance:** click a claimed business → popup shows the link; the
  `/hybridcard/{slug}` page renders name/category/contact from the pin; no
  pending row ever renders publicly.
- **Depends:** F1.4.

---

**F5.3 — "Get your Hybrid Card" funnel from the map**

- **What:** Unclaimed/unregistered business pins + the claim success screen
  get a CTA: "Own this business? Get your Hybrid Card" →
  `https://hybridcard.ai` onboarding (with `?src=localloop&district=<slug>`
  UTM so Phase 7 rev-share can attribute signups). Config-driven copy.
- **Acceptance:** CTA renders only for non-hybridcard pins; UTM params
  arrive on the card site (verify in its request logs); district param
  matches the active district (F8).
- **Depends:** F1.4 (F8.1 for district param — ship with `bondi` hardcoded
  first).

---

**F5.4 — Archetype assist surfaced to owners**

- **What:** In the popup for a hybridcard business (owner view / after
  claim), show "What your card can do" — the resolved skill list from
  `GET /api/archetypes/{archetype}/skills` (F2.4), e.g. a café sees
  menu-receptionist, daily-specials writer, review responder. Pure read-only
  discovery that drives owners into the card dashboard.
- **Acceptance:** popup for a `food` business lists the 7 food skills; API
  outage hides the section silently.
- **Depends:** F2.4, F5.2.

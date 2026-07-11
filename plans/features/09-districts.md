# 09 — Phase 8 — Multi-district in the Explore app (make it OBVIOUS)

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F8.1** — District registry on the map site
- [ ] **F8.2** — "Start a Local Loop in your area" (the growth loop, visible)
- [ ] **F8.3** — District-branded Looper dock

---


---

**F8.1 — District registry on the map site**

- **What:** llx11 reads the `district` table (anon read of approved rows):
  slug, name, center, radius. URL param `?district=<slug>` and a header
  **district switcher** (dropdown next to the logo: "Bondi · Byron Bay ·
  Rose Bay · …") that flies the camera to the district and scopes pins/news
  queries to its geofence (`ST_DWithin` filters already used by F6.2).
- **Acceptance:** switching districts moves the map + filters content; deep
  link `?district=byron-bay` lands zoomed on Byron; unknown slug falls back
  to Bondi.
- **Depends:** F7.1 (table), F3.4 (bus), F6.2 (geo RPC pattern).

---

**F8.2 — "Start a Local Loop in your area" (the growth loop, visible)**

- **What:** A prominent entry in the district switcher + footer card:
  "Run a Local Loop for your suburb — earn with your community" → form
  (name, email, suburb, existing FB group?) → writes
  `district_application` → notifies Bill → approved applications become
  `district` rows (status flow `applied→approved→live`).
- **Acceptance:** submission → row + email notification; approving (simple
  admin action in loop-onboard console) makes the district appear in the
  switcher after cache refresh.
- **Depends:** F8.1, F7.4.

---

**F8.3 — District-branded Looper dock**

- **What:** MicWave greeting + `speakResponse` intro use the active
  district ("Hey, Byron Bay Local Loop here…"); voice router's suburb
  defaults and radius center follow the active district.
- **Acceptance:** switch district → greeting text/voice changes; "find me a
  café" searches the new district's center.
- **Depends:** F8.1, F3.3.

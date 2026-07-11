# 08 — Phase 7 — `loop-onboard` (NEW repo): multi-district Facebook onboarding

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F7.1** — Scaffold `loop-onboard`
- [ ] **F7.2** — Member intake API + Facebook capture (verified July 2026 reality)
- [ ] **F7.3** — Welcome funnel (email-first)
- [ ] **F7.4** — District admin console + revenue share
- [ ] **F7.5** — Onboarding assistant (the "separate bot" for the group)
- [ ] **F7.6** — "Comment CARD" Private-Reply bot (pilot — the ONLY compliant automated DM)

---


> **Decision (recommended):** this is a NEW app in a NEW folder/repo
> `loop-onboard` — Bill creates the empty folder; the coding agent
> scaffolds it. It serves Bondi Local Loop first, but is **multi-district
> from day one** so Rose Bay / Bronte / Maroubra / Bondi Junction / Byron
> Bay admins can run their own funnel and earn their share.

---

**F7.1 — Scaffold `loop-onboard`**

- **What:** Next.js (same major version + conventions as new-card:
  TypeScript, App Router, Coolify standalone Dockerfile, `GET /api/health`)
  backed by **Supabase** (same project as the map — one community datastore).
  Tables (SQL migration in repo):
  `district` (slug, name, center_lat, center_lng, radius_m, fb_group_url,
  admin_name, admin_email, revshare_pct, status),
  `member` (id, district_slug FK, first_name, email UNIQUE-per-district,
  source `facebook|form|import`, fb_answers JSONB, referrer_name,
  consent_marketing bool, joined_fb_at, welcomed_at, card_claimed_at),
  `intake_log` (raw rows, idempotency key), `revshare_ledger` (district,
  period, attributed_signups, amount, status).
  Seed districts: bondi, byron-bay, rose-bay, bronte, maroubra,
  bondi-junction.
- **Acceptance:** `npm run dev` → health green; migration applies cleanly to
  staging Supabase; districts seeded.
- **Depends:** F0.3. Parallel-safe with everything.

---

**F7.2 — Member intake API + Facebook capture (verified July 2026 reality)**

- **Hard facts the design is built on (verified, sources in
  `.SEED/decisions.md`):** the Facebook **Groups API is dead** (removed
  April 2024 — no app can read member requests, answers, or approve
  members); membership-question answers are **only visible while a request
  is pending** (they vanish at approval, no export exists); Pages/apps
  **cannot cold-DM** members; Admin Assist can auto-approve + schedule
  welcome posts but can't capture or message.
- **What:** `POST /api/intake/member` — idempotent (hash of
  district+email+joined_fb_at), token-authenticated (`INTAKE_TOKEN` per
  district), accepting `{district, first_name, email, answers:{q1,q2,q3},
  referrer_name?, joined_fb_at, source}` — fed by THREE layers:
  1. **Layer 1 — official, zero risk, do immediately (no code):** reword
     membership Q2/Q3 so the email ask is explicit and opt-in ("Want the
     free Local Loop discount card? Leave your email"); Admin Assist
     auto-approves requests that answered all questions; weekly official
     Welcome Post (auto-tags up to 300 new joiners/7 days) + a pinned
     Admin-Assist recurring post, both linking to
     `join.localloop.ai/<district>` where email capture happens first-party
     with real consent.
  2. **Layer 2 — capture at approval (the main engine):** answers must be
     grabbed at the pending-request moment, in the admin's own browser.
     Options, same webhook target either way: Group Collector
     (~$297 lifetime, has webhooks + Sheets) / Groupboss (~$99/yr) — or a
     **self-built Chrome MV3 extension** (Bill has a dev account): a
     MutationObserver on the Member Requests page that, when the admin
     clicks Approve, POSTs the visible answers to `/api/intake/member`.
     Human-clicked approvals only (no bulk auto-approve), human pacing,
     dedicated Chrome profile, and prefer a second admin account for daily
     approvals — this technique breaches Meta ToS §3.2.3 in principle
     (risk = admin account restriction), though such tools have run for
     6+ years; Bill accepts/declines this trade-off explicitly.
  3. **Layer 3 — CSV/manual:** paste/upload page for anything captured by
     hand; always works, zero risk.
- **Acceptance:** posting the same member twice → one row; a CSV of 50 test
  rows imports with a per-row result report; invalid-email rows land in
  `intake_log` for manual fix, never crash; Layer 1 changes live in the
  Bondi group (screenshot evidence).
- **Depends:** F7.1.

---

**F7.3 — Welcome funnel (email-first)**

- **What:** On new member: send district-branded welcome email (provider:
  Resend or SMTP, env-driven; NO SMS in v1 — ACMA compliance lives in the
  card repo and is not re-solved here): "Welcome to <District> Local Loop —
  ① explore the local map (`localloop.ai/?district=<slug>`), ② claim your
  member discount card, ③ business owner? get your Hybrid Card
  (`hybridcard.ai?src=loop-onboard&district=<slug>`)."
  Member discount card v1 = a per-member QR page
  (`loop-onboard.../m/<member_code>`) reusing the VIP-pass verify pattern
  (HMAC-signed code) — full HybridCard VIP pass integration later.
  Double-entry consent: email footer unsubscribe + `consent_marketing`
  honored (Spam Act 2003: consent, identify sender, unsubscribe).
- **Acceptance:** test member → email arrives with working links + QR page
  renders; unsubscribe link flips consent and blocks further sends;
  `welcomed_at` set exactly once.
- **Depends:** F7.2.

---

**F7.4 — District admin console + revenue share**

- **What:** Login (Supabase Auth, email magic link) scoped per district:
  see member counts/conversion (welcomed → card claimed), edit welcome copy,
  upload CSVs, copy their intake token, view `revshare_ledger` (attributed
  hybridcard signups via the `?src=…&district=…` UTMs × `revshare_pct` —
  numbers visible from day one, payouts manual/monthly by Bill in v1).
- **Acceptance:** Bondi admin cannot see Byron data (RLS test); ledger shows
  a seeded attributed signup; copy edit changes the next welcome email.
- **Depends:** F7.3.

---

**F7.5 — Onboarding assistant (the "separate bot" for the group)**

- **What:** A LOOPER-brained chat endpoint + simple web chat on the welcome
  page ("Ask your Local Loop anything") that answers: what the group/map is,
  how the discount card works, how businesses join — powered by the looper
  API (search + archetype skills) with district context. Same
  suggest-then-confirm rules; it never messages anyone first.
- **Acceptance:** 10 scripted Q&A pairs answer correctly with district
  context; it refuses off-scope requests (no political content, no PII
  lookups).
- **Depends:** F7.3 (+F2.4 for business answers).

---

**F7.6 — "Comment CARD" Private-Reply bot (pilot — the ONLY compliant automated DM)**

- **What:** Meta kept exactly one group messaging path for apps: a Page can
  send **one Private Reply to a user's comment on a group post within
  7 days** (Page access token + `pages_messaging`, app subscribed to the
  `groups_feed` webhook field; private replies enabled in group settings).
  Build a tiny service in loop-onboard: welcome post says "Comment CARD and
  we'll DM you your Local Loop discount card" → webhook fires on comment →
  bot sends ONE private reply with the member-card link → if the user
  replies, the standard 24-hour window lets the bot collect their email
  conversationally.
- **Steps:** create the Meta app + Page token in Bill's dev account; App
  Review for `pages_messaging`; subscribe `groups_feed`; **validate with a
  test post first** — post-2024 webhook behaviour for groups is not
  well-documented in the wild, so this ships as a PILOT with a kill switch;
  log every send (one per commenter, ever) to stay inside policy.
- **Acceptance:** commenting CARD on the test post produces exactly one DM
  with a working card link; a second comment produces nothing; webhook
  outage degrades silently (welcome post still links to join page).
- **Depends:** F7.3. If the webhook proves dead, close the feature and note
  it in `.SEED/decisions.md` — Layers 1–3 carry the funnel.

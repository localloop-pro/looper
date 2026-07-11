# 10 — Phase 9 — Deploy & go-live (Coolify)

> Extracted verbatim from `plans/IMPLEMENTATION_PLAN.md` §5
> (v1.0, 2026-07-10; split 2026-07-11 per Bill's go-ahead).
> The master plan stays authoritative. Before implementing anything:
> read `SEED.md`, `.SEED/decisions.md`, `.SEED/gotchas.md`, and the
> master plan's Section 4 Golden Rules. Implement features in order;
> tick a box only when that feature's Acceptance criteria all pass.

## Checklist

- [ ] **F9.1** — Service map + DNS
- [ ] **F9.2** — Secrets, env + cron in production
- [ ] **F9.3** — Go-live smoke checklist (run WITH Bill, one item at a time)
- [ ] **F9.4** — Hot-zone flag flips (Bill-only decisions, in this order)

---


---

**F9.1 — Service map + DNS**

- **What:** On the existing Coolify server (`167.86.79.151`):
  | Service | Repo | Port | Domain |
  |---|---|---|---|
  | localloop-explore (exists) | localloop.pro-main | 3000 | localloop.ai |
  | looper-api (new) | looper | 8000 | api.localloop.ai |
  | typedb (new, internal) | image | 1729 | none (internal only) |
  | loop-onboard (new) | loop-onboard | 3000 | join.localloop.ai |
  | hybridcard (exists) | new-card | 3000 | hybridcard.ai |
  | looper-gateway (Cloudflare, exists) | worker | — | looper.localloop.ai |
  Fix the known `localloop.pro` Traefik default-cert/503 by re-issuing the
  cert or redirecting localloop.pro → localloop.ai at Cloudflare.
- **Acceptance:** all health endpoints green over HTTPS on their domains;
  TypeDB unreachable from the internet; `localloop.pro` no longer serves
  the default cert.
- **Depends:** F0.4, F7.1.

---

**F9.2 — Secrets, env + cron in production**

- **What:** Populate the Section 7 env table into Coolify secrets/worker
  secrets; register cron: new-card `bridge-drain` (`* * * * *`) +
  `rating-fire` (`*/5 * * * *`) (already specified in new-card CRON.md),
  looper `news_audio_worker` (`*/10 * * * *`), `brain/full_sync.py`
  (`0 3 * * *`).
- **Acceptance:** each cron shows a recent successful run in Coolify;
  secret-scan tests green; a signed test event flows in prod exactly as in
  F1.5 staging.
- **Depends:** F9.1.

---

**F9.3 — Go-live smoke checklist (run WITH Bill, one item at a time)**

1. `curl https://api.localloop.ai/health` → healthy.
2. Signed test deal → drain → approve pin → marker on localloop.ai.
3. "Hey Looper… find me a café" on the live site (Chrome, phone + laptop).
4. News test post → audio plays; Byron coords can't fetch Bondi news.
5. Test member CSV → welcome email → QR member page.
6. District switcher: Bondi ↔ Byron.
7. Ricky desktop: "any deals waiting?" (read-only cockpit).
8. Rollback notes per service (Coolify redeploy previous image; worker
   `wrangler rollback`; RLS changes have down-migrations).
- **Acceptance:** all 8 checked with screenshots archived in
  `plans/evidence/F9.3/`; ROLLBACK section filled in.
- **Depends:** everything above.

---

**F9.4 — Hot-zone flag flips (Bill-only decisions, in this order)**

1. new-card: set `LOOPER_INGEST_URL` + `LOCALLOOP_BRIDGE_URL` + secrets in
   PROD (bridge outbound goes live — Phase 11 of the card roadmap).
2. Watch one week of `bridge_events` + dead-letter counts.
3. Only then consider (card-repo governance, separate sign-offs):
   `LIVE_ALERT_FANOUT`, `SMS_LIVE`, `PAYMENTS_LIVE`, VAPID push.
- **Acceptance:** each flip logged in `.SEED/decisions.md` with date +
  reason; dead-letter count stays 0 for 7 days before the next flip.
- **Depends:** F9.3.

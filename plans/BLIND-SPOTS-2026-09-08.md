# Blind spots and next steps (2026-09-08)

**Who this is for:** Bill. **What it is:** an outside read of all three repos plus
live probes of production, written so a beginner can act on it one step at a time.
**Home:** `looper/plans/` because it spans looper, LocalLoop Explore (llx11) and
HybridCard. Every claim below is either a file in the repos or a `curl` you can rerun.

---

## 1. The one-paragraph answer

The plumbing is real and mostly working. All four services answer their health
checks, the HybridCard bridge is live and has processed 180 signed events, the
receivers have HMAC tests, and the anti-bias rules are enforced by tests. The blind
spots are not in the code. They are in what a stranger experiences today:

- the live map's voice brain is pointed at `localhost`, so "Hey Looper" is offline
  for every visitor;
- the production brain holds 4 businesses, 0 reviews and 1 deal, so "find me a
  café" returns nothing even after the wiring is fixed;
- two of those 4 businesses link to `http://localhost:3000` card pages;
- analytics is switched off, so nobody knows whether anyone visits;
- the public review endpoint lets anyone post a "verified visit" review with no
  login, so the honest-ranking promise can be gamed today;
- the 156K-member Facebook group has no funnel at all, while the last month of
  effort went into a bookings calendar for one salon.

**Refined idea to test today:** *one suburb, one loop.* A stranger opens
localloop.ai on their phone, says "Hey Looper, find me a hairdresser", hears
three real Bondi options, taps "View card", and lands on a working card page.
Everything else (TypeDB, tokens, districts, bookings phases 4 to 10) waits until
10 strangers have completed that loop.

---

## 2. What is actually live today (probed 2026-09-08 04:00 UTC)

Rerun any row with the command in the last column.

| Check | Result | Command |
|---|---|---|
| looper API health | 200 healthy | `curl -s https://api.localloop.ai/health` |
| looper gateway (Cloudflare Worker) | 200 ok | `curl -s https://looper.localloop.ai/health` |
| LocalLoop map health | 200 ok, `commit: ""` | `curl -s https://localloop.ai/health.json` |
| HybridCard health | 200 ok | `curl -s https://hybridcard.ai/api/health` |
| localloop.pro | TLS error, self-signed Traefik cert (broken since May) | `curl -sI https://localloop.pro/` |
| Bridge events received | 180 total: 131 card.upserted, 48 card.removed, 1 deal.upserted | `curl -s https://api.localloop.ai/api/ingest/status` |
| Businesses in the production brain | 4 (Qikflo, Aesthete Hair, Bill Minglis, Bondi Local Loop), all category `professional` | `curl -s https://api.localloop.ai/api/businesses` |
| Community reviews in production | 0 on every business | same as above, see `review_count` |
| Search "cafe" at Bondi | 0 results | `curl -s "https://api.localloop.ai/api/search?q=cafe&lat=-33.8908&lng=151.2748"` |
| Search "hair" at Bondi | 1 result, `card_url: http://localhost:3000/c/aesthete-hair` | `curl -s "https://api.localloop.ai/api/search?q=hair&lat=-33.8908&lng=151.2748&radius=20000"` |
| Map site `LOOPER_API_URL` | **empty string** in the 2026-09-07 build | `curl -s https://localloop.ai/assets/js/env.js \| grep LOOPER_API_URL` |
| Map site analytics config | `ANALYTICS_BEACON_URL: ""`, `ANALYTICS_USE_SUPABASE: ""` | `curl -s https://localloop.ai/assets/js/env.js \| grep ANALYTICS` |
| Jarvis voice scripts on the live page | all 5 loaded (`assets/js/jarvis/*.js`) | `curl -s https://localloop.ai/ \| grep -o 'assets/js/jarvis/[a-z-]*.js' \| sort -u` |
| HybridCard homepage rating | hardcoded "4.8, 128 reviews" demo number is live | `curl -s https://hybridcard.ai/ \| grep -o '128 reviews[^"]*'` |
| Aesthete public card | 200 (the 2026-09-08 todo item saying 404 looks stale) | `curl -sI https://hybridcard.ai/c/aesthete-hair` |

Not probed here: Supabase pin counts (the session's permission gate blocked a
read-only count). Your own 2026-09-08 review already flagged that the anonymous
pin read returned a rejected row, so treat that as open.

---

## 3. Blind spots, ranked by how much they hurt

### 3.1 The live map's brain is switched off

- **Evidence:** `LOOPER_API_URL` is an empty string in the production `env.js`
  built 2026-09-07. `config.js` maps it to `looperApi`, and `index.html` falls back
  to `http://localhost:8000`. The five Jarvis scripts are loaded and will call
  localhost from every visitor's browser.
- **History:** diagnosed 2026-07-28 (`.SEED/gotchas.md`, first entry). The fix was
  handed to you as an env var on the llx11 Coolify app. Six weeks later it is still
  unset.
- **Why it matters:** every "Hey Looper" on the public site says the brain is
  offline. All the voice work of Phases 3 and 4 is invisible.
- **Smallest fix:** set one env var and redeploy. See step 1 in section 5.

### 3.2 The production brain is empty

- **Evidence:** 4 businesses, all `professional`, 0 reviews, 0 pins, 1 deal ever.
  "cafe" and "café" both return zero.
- **Why:** the only way a business enters Looper in production is the HybridCard
  bridge, and HybridCard has 7 card businesses in total. The 20-business Bondi seed
  only ever ran on laptops.
- **Hidden architecture gap:** the map already has a Business Truth Layer of
  claimed, moderated business pins in Supabase. Looper never reads it. So the voice
  brain's coverage equals the number of HybridCard customers, not the number of
  businesses on the map. Two directories, no sync.
- **Do not** run `backend/seed.py` against production, in any form. It plants 11
  fabricated reviews from a "Demo" user with `verified_visit=True`, which breaks
  anti-bias rule 4 (reviews attributed to real users). Even with the reviews
  stripped, the business list is test data: `LocalLoop Pharmacy`, `Bondi Plumbing
  Co` and `Bondi Hair Studio` are not verified listings, and search would send
  strangers to addresses that may not exist. Production content has to come from
  the moderated Business Truth Layer or a verified import (section 4, item 1).

### 3.3 Localhost URLs leaked into production data

- **Evidence:** `card_url` for Bill Minglis and Aesthete Hair is
  `http://localhost:3000/c/...`. Qikflo points at `card.localloop.ai`, the old Mac
  tunnel. Only the `website` field for Aesthete is a real `hybridcard.ai` URL.
- **Why:** the Card URL contract says receivers store whatever HybridCard sends,
  and HybridCard emits localhost URLs whenever it runs outside `NODE_ENV=production`.
  Dev sends reached the production receiver and stale rows stay until re-ingest.
- **Why it matters:** every "View card" link from the voice brain is dead for the
  public.
- **Detail that matters:** `resolve_card_url()` in `backend/routes/search.py`
  prefers an active deal's `public_card_url` over the business `website`. Aesthete
  has the one active deal, so its localhost link comes from that deal, not the
  card. Re-sending the card alone will not fix it.
- **Fix:** re-send the deal and the cards from hybridcard.ai (step 4). Do not
  change the receivers: the Card URL contract in `.SEED/gotchas.md` is frozen and
  requires them to store allowed loopback URLs as-is so local dry runs keep
  working. Close the hole at the sender boundary instead: a dev or tunnel
  HybridCard must never carry the production `LOOPER_INGEST_URL`,
  `LOOPER_CARD_INGEST_URL` or `LOCALLOOP_BRIDGE_URL`, and non-production senders
  should sign with their own key id (for example `hc-dev`) that production
  receivers do not list in `HYBRIDCARD_KEY_IDS`. The key-id lookup is already part
  of the contract, so this needs no contract change.

### 3.4 Nothing is measured

- **Evidence:** analytics config empty in production, `commit` empty in
  `health.json`, no dashboard anywhere, no user or visit number in any status file.
  `PROJECT_INTENT.md` set targets in May (1,000 users in 3 months) and nothing has
  measured against them.
- **Why it matters:** you cannot find blind spots without a number. Every "what
  next" decision is currently a guess.
- **Fix:** SPEC-013 already has the table and the script. Turn it on (step 5).

### 3.5 The reviews cold-start blocks the core promise

- **Promise:** ranked by genuine community reviews, never by money.
- **Reality:** 0 reviews. The Facebook review importer runs in demo mode only.
  HybridCard VIP ratings unlock only after a verified interaction, and every verified
  interaction path needs SMS OTP (`SMS_LIVE=false`) or payments (`PAYMENTS_LIVE=false`).
- **Result:** the ranking degrades to text match then distance, which is what
  Google Maps already does better.
- **Not yet considered:** a plan for the first 100 reviews that does not depend on
  flipping money or SMS switches. Candidates: a paper QR at Aesthete's counter that
  opens a review form gated by a merchant-scanned pass (already built), or a
  one-question review post in the Facebook group linked to a review URL.

### 3.6 Anyone can plant a "verified" review today

- **Evidence:** `POST /api/reviews` in `backend/routes/reviews.py` has no
  authentication, takes `user_id` from the request body, and copies the
  caller-supplied `verified_visit` flag straight into a public review.
  `POST /api/onboard` creates a user from any syntactically valid mobile number
  with no OTP. Both are live on `api.localloop.ai` right now.
- **Why it matters:** review count is the first ranking input after text match.
  Two unauthenticated requests are enough to push any business up, with a
  "verified visit" badge. This contradicts section 3.5, which assumed verified
  reviews needed SMS or payments. It also means the "genuine community reviews"
  promise is falsifiable by anyone who reads the API docs at `/docs`.
- **Fix (before any public invite):** either disable public review submission
  behind an env flag until a verified path exists, or keep the endpoint but derive
  `verified_visit` server-side (always `false` for direct submissions) and require
  a signed member code. This touches auth, so it is owner-gated. See step 8.

### 3.7 Every gate leads to you, and you are the bottleneck

- **Evidence:** `plans/COMPLETION_STATUS.md` lists eight packages "waiting on Bill":
  pin approvals, TypeDB deploy, TTS cost, voice acceptance, staging proof, flag flips.
  In HybridCard: SMS, payments, alert fan-out, push, Polar. In LocalLoop: TLS,
  Pages env vars, branch protection, Supabase target.
- **Why:** the agents have correctly refused to touch production. But there is no
  staging where the switches are ON, so the only place anything is ever proven
  end-to-end is production, with you present.
- **Not yet considered:** one staging environment per repo where `SMS_LIVE` sends
  to a test number pool and payments use the Polar sandbox. Agents then prove the
  whole flow and you flip production once, with evidence.

### 3.8 Distribution is the asset and it has zero build

- **Evidence:** 156K plus 6K members. Phase 7 (loop-onboard) has not started.
  Meanwhile the last 30 days: 110 commits in HybridCard, mostly Bookings for one
  salon; 20 in looper (0 in the last 7 days); 3 in LocalLoop.
- **Why it matters:** a bookings engine competes with Timely, Fresha and Square
  Appointments, which are free or near free. The Facebook groups are something
  nobody else has.
- **Free today:** Layer 1 of F7.2 needs no code. Reword membership question 2 to
  an opt-in email ask, and pin a welcome post that links to localloop.ai with a
  tracking parameter. Step 7.

### 3.9 The Facebook capture plan bets the crown jewel

- **Evidence:** F7.2 Layer 2 (a browser extension scraping member requests at
  approval time) is recorded as a Meta ToS breach "in principle" with the risk
  landing on the admin account of the 156K group. The plan says you accept or
  decline the trade-off explicitly. No decision is recorded.
- **Recommendation:** decline Layer 2 for now, in writing, in `.SEED/decisions.md`.
  Layers 1 and 3 carry the funnel with zero risk. Revisit only with measured
  conversion numbers from Layer 1.

### 3.10 Fake social proof on a "genuine reviews" brand

- **Evidence:** hybridcard.ai homepage shows a hardcoded 4.8 rating from 128
  reviews. `.seed/decisions.md` calls it "visual/copy only".
- **Why it matters:** the whole pitch is honesty in rankings. Anyone who checks
  finds a made-up number on the front door.
- **Fix:** show the real blend or "No ratings yet". Small change in
  `LocalLoopHybridCard.ReviewStars` and the homepage fallback props.

### 3.11 Process weight is larger than the team

- **Evidence (LocalLoop repo):** 244 markdown files versus 198 code files, 599
  unchecked boxes, 13 governance rules, plus FollowMe, HANDOFF, three continuity
  layers, RAMP, Hermes, autoforge, Codex, Cursor, pi and Claude conventions all
  active at once.
- **Evidence (looper):** three status documents disagree. `plans/BOT_HANDOFF.md`
  says Phases 2 to 9 are not started. `plans/COMPLETION_STATUS.md` says they are
  code complete. `plans/features/03-05` are unticked. Live probes show the Looper leg of the
  F9.4 "flag flip" is already live (180 events) while its box is unticked. The
  map-pin leg was not probed here, so the box may be honest, but nothing records
  which.
- **Evidence (LocalLoop `CLAUDE.md`):** the file is an autoforge "spec creation
  assistant" prompt with a hardcoded Mac path. Any Claude session opened in that
  repo is told to run a project interview instead of following `AGENTS.md`.
  The repo also has no `SEED.md` or `.SEED/`, unlike the other two.
- **Why it matters:** for a beginner owner the docs are the product's memory, and
  the memory contradicts itself. Agents then re-derive state every session, which is
  where the drift comes from.
- **Fix:** one status file per repo, updated weekly in 10 lines; archive the rest;
  point `CLAUDE.md` at `AGENTS.md`; create `SEED.md` and `.SEED/` in LocalLoop.

### 3.12 Single points of failure

- HybridCard production ran on your Mac behind a Cloudflare tunnel until this
  month (`OPS.md`). Secrets live in `secrets/*.env` on that Mac. The Coolify
  password was lost once (2026-07-21).
- The looper SQLite database sits on one Docker volume with no backup mentioned
  anywhere.
- `api.localloop.ai` reaches its origin over plain HTTP
  (`http://looper-api.167.86.79.151.sslip.io`). Payloads are public-safe by design
  so this is low risk, but the origin is also reachable directly, bypassing
  Cloudflare.
- Bus factor is one person, and that person is also product owner, group admin,
  tester and approver.

### 3.13 Privacy footprint growing faster than the rules

- Looper's `users` table stores raw mobile numbers and names, for a Telegram bot
  that never launched. The VIP Network spec (HybridCard) says "hash, never raw".
  The looper repo has no privacy policy; the map site does.
- Fix: hash or delete the looper onboarding mobile field, or remove `/api/onboard`
  if Telegram is dead.

### 3.14 Dead scope still carried in the docs

Telegram bot (waiting on a token since May), Hermes profile, HuggingFace
fine-tuning, TypeDB Cloud on AWS, Kaspa KRC-20 token, device sync, wallet passes,
Discourse SSO, Bubble. Each one costs attention in every agent session. Write a
"not now" list and stop referencing them.

### 3.15 No human other than you has used the voice

Every voice acceptance item reads "Bill's live-mic acceptance still owed". Web
Speech needs Chrome or Safari over HTTPS. No stranger has tried it. Once 3.1 and
3.2 are fixed, watch five people from the group use it on their own phones.

---

## 4. Things you have not considered yet

1. **Looper should read the map's approved business pins.** That is the fastest
   way to fill the brain with real, moderated local businesses. It is a small
   nightly sync from Supabase into `businesses`, using the existing haversine
   suburb logic. It also makes the map and the voice agree.
2. **A review path that needs no SMS and no payments.** The merchant pass scan
   already exists in HybridCard. A printed QR at one counter unlocks one real
   review at a time.
3. **Staging with the switches on.** See 3.7. Without it the safety posture is a
   delivery blocker forever.
4. **A weekly number.** Visitors, voice queries, claims, cards. Four numbers on one
   line, every Monday, before any building decision.
5. **What you say no to.** Bookings phases 4 to 10, TypeDB in production, tokens,
   districts. None of them change the stranger's first minute on the map.
6. **Backups and a rollback drill.** SQLite volume, Mongo, and the Supabase plan
   tier. Your own 2026-09-08 review lists the rollback drill; it is still open.

---

## 5. The test-today plan: "one suburb, one loop"

Do these in order. Each step ends with a check you can paste into a terminal.
Stop after any step whose check fails and fix that first.

**Success rule for the whole plan:** 10 strangers say "Hey Looper, find me a
hairdresser", hear at least 2 options, tap "View card", and land on a working
page. Count them. That number decides what gets built next. The loop needs
businesses that have a card, because only card holders carry a "View card" link.
Today that means the HybridCard businesses (Aesthete Hair and Qikflo), so the
test is the hairdresser flow until more real cards exist.

### Step 1: switch the brain on (5 minutes, Coolify UI)

1. Log in to Coolify at `http://167.86.79.151:8000`.
2. Open the LocalLoop Explore app (id `zl9s2tebckbu9zgzkdy2en4t`).
3. Environment Variables: add `LOOPER_API_URL` with value
   `https://api.localloop.ai`. Save.
4. Redeploy.
5. Check:

```bash
curl -s https://localloop.ai/assets/js/env.js | grep LOOPER_API_URL
```

Expect `LOOPER_API_URL: "https://api.localloop.ai"`. Then open localloop.ai in
Chrome on your phone, tap the Looper face, say "find me a hairdresser". You should
hear Aesthete Hair. That is the whole voice stack working in public for the first
time.

### Step 2: make the redirect for localloop.pro (5 minutes, Cloudflare)

Cloudflare dashboard, zone `localloop.pro`, Rules, Redirect Rules, create a
wildcard rule: source `https://localloop.pro/*` and a second one for
`https://www.localloop.pro/*`, target `https://localloop.ai/${1}`, status 301.
Cloudflare writes the captured wildcard as `${1}`, not `$1`. Make sure the DNS
records are proxied (orange cloud). Check root and a non-root path:

```bash
curl -sI https://localloop.pro/ | grep -i -E 'HTTP|location'
curl -sI https://localloop.pro/news.html | grep -i -E 'HTTP|location'
```

Expect `301` and `location: https://localloop.ai/` on the first, and
`location: https://localloop.ai/news.html` on the second. The broken Traefik
certificate stops mattering because the origin is never reached.

### Step 3: decide where real businesses come from (decision, no commands)

Do not seed production. `backend/seed.py` is test data with fabricated reviews
and unverified listings (section 3.2), and the running container has the old
script baked into its image anyway. The only honest sources are:

1. the map's moderated Business Truth Layer in Supabase (approved claim pins),
   read nightly into Looper's `businesses` table, or
2. a list of businesses you have personally verified, imported by a script.

Option 1 is a small build (section 4, item 1) and is the first thing to unfreeze
after step 9. Until it lands, the loop is tested with card-holding businesses
only, which is why the success rule uses the hairdresser.

### Step 4: repair the localhost card links (HybridCard admin, 10 minutes)

Two different rows are stale, and they need two different re-sends because
Looper prefers an active deal's URL over the card's URL:

1. **Aesthete Hair** carries the one active deal. On hybridcard.ai open Deals,
   edit that deal and save it (or pause then publish it). That re-enqueues a
   `deal.upserted` event with the production URL.
2. **Bill Minglis** has no deal. Open My Cards, toggle any capability off and on.
   That re-enqueues a card upsert.

The drain runs every minute. Then:

```bash
curl -s "https://api.localloop.ai/api/discover?suburb=Bondi" | grep -c localhost
curl -s "https://api.localloop.ai/api/search?q=hair&lat=-33.8908&lng=151.2748&radius=20000" | grep -o '"card_url":"[^"]*"'
```

Expect `0` on the first and a `hybridcard.ai` address on the second. Do not
change the receivers to drop loopback URLs: the frozen Card URL contract requires
them to keep allowed loopback addresses as-is for local dry runs. Close the hole
at the sender instead, as described in section 3.3: no production receiver URLs
in any dev `.env.local`, and a separate key id for non-production senders.

### Step 5: turn on measurement (Supabase + Coolify, 15 minutes)

1. The spec lives in the LocalLoop repo (`localloop.pro-main`), file
   `.governance/specs/SPEC-013-analytics-and-health.md`. The SQL from it is
   pasted here so you do not need the other repo. Open the Supabase dashboard,
   project `ggmzagbvzbwkdqdomzda` (the one in the live `env.js`), SQL editor,
   and run:

```sql
create table if not exists public.analytics_events (
  id bigserial primary key,
  event text not null,
  session_id text,
  props jsonb,
  created_at timestamptz default now()
);
-- RLS: anon may insert, no select.
alter table public.analytics_events enable row level security;
create policy "anon insert" on public.analytics_events for insert to anon with check (true);
```

   This is a production migration. It only adds one new table and one insert
   policy; it changes nothing that exists.
2. On the LocalLoop Coolify app set `ANALYTICS_USE_SUPABASE=true` (the exact
   string `true`; `analytics.js` compares against it). Redeploy.
3. Visit localloop.ai once, then in the SQL editor run:

```sql
select event, count(*) from public.analytics_events group by event;
```

   Expect at least one `page_view` row. Anon has no select, so run this as the
   dashboard user, not from the browser.

From now on you have a visitor count. Also set `COMMIT` in the build so
`health.json` tells you what is deployed.

### Step 6: remove the fake rating (code, small)

On the HybridCard homepage fallback card, pass no `rating` and no `ratingCount`.
The stars render hollow and the popover is not shown. Check:

```bash
curl -s https://hybridcard.ai/ | grep -c '128 reviews'
```

Expect `0`.

### Step 7: open the free funnel (Facebook admin, no code, 20 minutes)

1. Pin a welcome post: "Say hi to Looper. Open localloop.ai on your phone, tap the
   face, and ask for what you need." Use the link
   `https://localloop.ai/?src=fb-bondi`.
2. Leave the membership questions as they are for now. Do not ask for an email
   yet: with Layer 2 declined and no first-party join page built, an email typed
   into a membership answer vanishes at approval and nothing can deliver the card
   it promised. Add the email ask only when `join.localloop.ai` (F7.1 to F7.3)
   exists to capture it with consent.
3. Record in `.SEED/decisions.md`: Layer 2 (extension capture) declined for now.

After step 5 you will see `page_view` rows and can count how many came from the
post.

### Step 8: close the open review door (code, owner-gated)

Before inviting anyone, fix section 3.6. Smallest safe change in
`backend/routes/reviews.py` and `backend/routes/users.py`: put both public
write endpoints behind `LOOPER_PUBLIC_WRITES=false` (return 403 in production
until a verified path exists), and never read `verified_visit` from the body.
This is an auth-adjacent change to a live API, so say yes before it is built.
Check after deploy:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.localloop.ai/api/reviews \
  -H "Content-Type: application/json" \
  -d '{"business_id":3,"user_id":1,"rating":5,"review_text":"x","verified_visit":true}'
```

Expect `403`.

### Step 9: watch ten strangers, five at a time

Ask five members to try it on their own phones while you watch. Write down every
place they got stuck. Fix the blockers, then run a second round of five. The
success rule needs ten completions, so do not evaluate it after the first five.
That list of stuck points is the real backlog.

---

## 6. What to freeze for two weeks

- Bookings phases 4 to 10.
- TypeDB in production, TypeDB Cloud, DB2 telemetry.
- Tokens, Deal Passes, Kaspa.
- Districts and loop-onboard code (the Facebook Layer 1 changes above are not code).
- Any new agent framework, governance rule or planning document.

Unfreeze when the section 5 success rule has a number next to it.

---

## 7. Process recommendation

1. One `STATUS.md` per repo, 10 lines, updated every Monday: what is live, the
   four numbers, the one thing being built, the one thing blocked and on whom.
2. Retire `BOT_HANDOFF.md` and `COMPLETION_STATUS.md` into that file.
3. Fix LocalLoop `CLAUDE.md` to be `@AGENTS.md` and add `SEED.md` plus `.SEED/`
   there, matching the other two repos.
4. Record in `.SEED/decisions.md` that the Looper leg of F9.4 item 1 is live
   (180 events as of 2026-09-08). Do not tick the box yet: it needs the map-pin
   leg proven too (a Supabase count of `source=hybridcard` pins, which this audit
   could not run) and the seven-day dead-letter watch from F9.4 item 2.

---

## 8. Good news, so this is fair

- Four services healthy, bridge live, 180 events processed, idempotency holding.
- HMAC receivers with test matrices on both sides. Anti-bias enforced by tests.
- HybridCard's security chokepoints (`toPublic`, 404-not-403, atomic wallet,
  BYOK vault, SSRF guard) are genuinely good.
- Secret scanning in CI in two repos. Kill switches fail closed.
- The Jarvis voice stack is fully embedded in the live page. It only needs step 1.

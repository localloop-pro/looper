# Blind spots and next steps (2026-09-08)

**Who this is for:** Bill. **What it is:** an outside read of all three repos plus
live probes of production, written so a beginner can act on it one step at a time.
**Home:** `looper/plans/` because it spans looper, LocalLoop Explore (llx11) and
HybridCard. Every claim below is either a file in the repos or a `curl` you can rerun.

---

## 1. The one-paragraph answer

The plumbing is real and mostly working. All four services answer their health
checks, the HybridCard bridge is live and has processed 180 signed events, the
receivers have HMAC tests, and tests keep discounts, source and `rank_boost` out
of the ranking (section 8 says what they do not cover). The blind spots are
mostly not in the code. They are in what a stranger experiences today:

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
| Search "hair" at Bondi | 1 result, `card_url: http://localhost:3000/c/aesthete-hair` | `curl -s "https://api.localloop.ai/api/search?q=hair&lat=-33.8908&lng=151.2748&radius_km=20"` |
| Map site `LOOPER_API_URL` | **empty string** in the 2026-09-07 build | `curl -s https://localloop.ai/assets/js/env.js \| grep LOOPER_API_URL` |
| Map site analytics config | `ANALYTICS_BEACON_URL: ""`, `ANALYTICS_USE_SUPABASE: ""` | `curl -s https://localloop.ai/assets/js/env.js \| grep ANALYTICS` |
| Jarvis voice scripts on the live page | all 5 loaded (`assets/js/jarvis/*.js`) | `curl -s https://localloop.ai/ \| grep -o 'assets/js/jarvis/[a-z-]*.js' \| sort -u` |
| HybridCard homepage rating | hardcoded demo rating is live (`Rated 4.4 out of 5 from 128 reviews`) | `curl -s https://hybridcard.ai/ \| grep -o '128 reviews[^"]*'` |
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
  tunnel, which now answers 502 (probed 2026-09-08). Only Bondi Local Loop and
  Aesthete's `website` field carry a real `hybridcard.ai` URL.
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
  with no OTP. `POST /api/pins` in `backend/routes/map.py` writes a map pin from
  any caller with no authentication at all. Two reads leak as well:
  `GET /api/users/{id}` returns first name, interest, join code and signup time
  for any sequential id, and `GET /api/code/{code}` lets anyone test join codes.
  All of these are live on `api.localloop.ai` right now.
- **Why it matters:** review count is the first ranking input after text match.
  Two unauthenticated requests are enough to push any business up, with a
  "verified visit" badge. This contradicts section 3.5, which assumed verified
  reviews needed SMS or payments. It also means the "genuine community reviews"
  promise is falsifiable by anyone who reads the API docs at `/docs`.
- **Fix (before any public invite):** put the three public writes (reviews,
  onboard, pins) and the two profile reads (`/api/users/{id}`, `/api/code/{code}`)
  behind one env flag until a verified path exists, or keep them but derive
  `verified_visit` server-side (always `false` for direct submissions), require a
  signed member code, and strip join codes from any public response. This touches
  auth, so it is owner-gated. See step 7.

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
- **Free today:** a pinned welcome post that links to localloop.ai needs no
  code (step 9, after the step 7 lockdown and the step 8 two-option check). Do not add an email ask to the membership questions yet: with
  no capture page, the answer vanishes at approval. That ask waits for
  `join.localloop.ai` (F7.1 to F7.3).

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
- The Coolify admin console is used over plain `http://` at a public IP.
  Anyone on the network path can read the login and take over every
  deployment. Use an SSH tunnel or an HTTPS instance domain (step 1) and
  rotate the password afterwards.
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

### 3.16 The first real test already found a matching bug (2026-09-08)

- **Evidence:** after step 1 went live, "Hair dresser" (two words) found
  Aesthete Hair and "Hairdresser" (one word) found nothing, typed or spoken.
- **Why:** `backend/routes/search.py` matches each query word as a substring of
  the name, category, suburb or description. "hair" is inside "Aesthete Hair";
  "hairdresser" is not. The voice router's synonym table
  (`web/jarvis/voice-command-router.js`) knows "hair" and "barber" but not
  "hairdresser" or "salon", and the card is filed under `professional`, so
  category words cannot rescue it either.
- **Fix, two halves:** (a) on hybridcard.ai set Aesthete's industry to Health &
  Beauty, sub-type Salon, so the card re-sends with category `health`; (b) a
  small backend normalisation table that expands everyday compound words and
  synonyms before matching (hairdresser and hairdressers to hair and salon,
  barber to hair, cafe to coffee), with a regression test. Not a blanket
  "query word contains name word" rule: that would let "carpet cleaner" match a
  business called "Car Wash" and push real matches out of the five-result
  limit. Half (b) is owner-approved code work and a Coolify redeploy of
  looper-api.

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
7. **Decide the ranking order and write it down.** Today text relevance comes
   first, then review count, then distance. Either amend AGENTS.md rule 1 to say
   "match quality first, then reviews, recency, proximity", or change the sort
   to reviews first among equally matching businesses, and add a test either
   way. With zero reviews in production the two orders give identical results,
   so this is a decision for before the first real reviews land, not a launch
   blocker.

---

## 5. The test-today plan: "one suburb, one loop"

Do these in order. Each step ends with a check you can paste into a terminal.
Stop after any step whose check fails and fix that first.

**Success rule for the whole plan:** 10 strangers say "Hey Looper, find me a
hairdresser", hear at least 2 options, tap "View card", and land on a working
page. Count them. That number decides what gets built next. The loop needs
businesses that have a card, because only card holders carry a "View card" link.
Today that means the HybridCard businesses (Aesthete Hair and Qikflo), so the
test is the hairdresser flow until more real cards exist. Production returns
exactly one hairdresser today, and the anti-bias rule says always show multiple
options, so a second real salon or barber with a card is a prerequisite for any
public traffic (step 8). Until then, steps 1 to 7 prove the mechanics only.

### Step 1: switch the brain on (5 minutes, Coolify UI)

1. Open Coolify over an encrypted path, not the plain `http://` address. The
   simplest is an SSH tunnel from your Mac, then the browser talks to your own
   machine:

```bash
ssh -L 8001:127.0.0.1:8000 root@167.86.79.151
```

   Leave that window open and browse to `http://localhost:8001`. Local port 8001
   is used on purpose: on your Mac, port 8000 is already taken by TypeDB
   (`.SEED/gotchas.md`). Without a terminal, the same tunnel is a Termius
   Port Forwarding rule: Local, local port `8001`, bind `127.0.0.1`,
   intermediate host `167.86.79.151`, destination `127.0.0.1` port `8000`,
   then double-click the rule to start it. **Verified 2026-09-08:** that rule
   connected on port 22 with the saved root credentials and served the Coolify
   login at `localhost:8001`. The 2026-07-21 note in `plans/evidence/F9.1/`
   saying port 22 was refused is stale. The longer-term
   fix is a Coolify instance domain with HTTPS (Settings, Instance Domain, for
   example `coolify.localloop.ai`). Because the admin login has been used over
   plain HTTP until now, change the Coolify password once you are on the
   encrypted path.
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

**Executed 2026-09-08:** the variable is set, the site redeployed, and the map
answered from production. On "always show multiple options": the brain
currently holds one hairdresser, and the answer says so in plain words ("the
only match"). A truthful single result is not a ranking claim, and the
alternative (leaving the brain pointed at localhost) showed visitors an error
instead. Voice therefore stays on, and the two-option prerequisite is enforced
before any stranger is recruited (step 8), not before the wiring fix.

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

Three rows are stale, and they need two different kinds of re-send because
Looper prefers an active deal's URL over the card's URL:

1. **Aesthete Hair** carries the one active deal. On hybridcard.ai open Deals,
   edit that deal and save it (or pause then publish it). That re-enqueues a
   `deal.upserted` event with the production URL.
2. **Bill Minglis** and **Qikflo** have no deal. Qikflo's link points at the old
   Mac tunnel `card.localloop.ai`, which now answers 502. For each card open My
   Cards, toggle any capability off and on. That re-enqueues a card upsert.
3. **Bondi Local Loop** already carries a `hybridcard.ai` link; leave it.

The drain runs every minute. Then fetch the full list and look at every link:

```bash
curl -fsS "https://api.localloop.ai/api/discover?suburb=Bondi&radius_km=20" -o /tmp/discover.json \
  && grep -oE '"name":"[^"]*"|"card_url":(null|"[^"]*")' /tmp/discover.json | paste - -
```

The first command must succeed. Expect four lines, and every `card_url` on a
`hybridcard.ai` host: no `localhost`, no `card.localloop.ai`, no `null`. Do not
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
drop policy if exists "anon insert" on public.analytics_events;
create policy "anon insert" on public.analytics_events for insert to anon with check (true);
```

   This is a production migration. It only adds one new table and one insert
   policy; it changes nothing that exists, and it is safe to run twice because
   the policy is dropped and recreated rather than duplicated.
2. On the LocalLoop Coolify app set `ANALYTICS_USE_SUPABASE=true` (the exact
   string `true`; `analytics.js` compares against it). Redeploy.
3. Visit localloop.ai once, then within ten minutes run this in the SQL editor:

```sql
select event, created_at
from public.analytics_events
where created_at > now() - interval '10 minutes'
order by created_at desc limit 5;
```

   Expect at least one `page_view` row stamped in the last few minutes. The
   time window matters: an all-time count could pass on a row left by an
   earlier test while the new deployment sends nothing. Anon has no select, so
   run this as the dashboard user, not from the browser. That query is the ingestion smoke
   check only. The number to watch weekly is visitors, not events, because one
   person reloading counts many times:

```sql
select count(distinct session_id) as visitors_last_7_days
from public.analytics_events
where event = 'page_view' and created_at > now() - interval '7 days';
```

   Treat these numbers as indicative, not proof. The insert policy accepts any
   row from the public anon key, which is how a cookie-free, tracker-free
   analytics module has to work, so anyone who wants to can inflate them. A
   sudden spike with no matching Facebook post is suspect. If the numbers ever
   start driving money decisions, move ingestion behind a rate-limited endpoint
   (the `ANALYTICS_BEACON_URL` path through a Worker or n8n) that validates the
   payload before it reaches the table.

From now on you have a visitor count.

**Commit marker (small LocalLoop code change, not a click).** `health.json`
shows `commit: ""` because `scripts/build-health.js` and `scripts/inject-env.js`
only read `GIT_COMMIT` or `RAILWAY_GIT_COMMIT_SHA`, then fall back to
`git rev-parse HEAD`, which fails inside the Coolify build. Coolify sets
`SOURCE_COMMIT` on every build, so add it to the fallback chain in both scripts:

```js
process.env.GIT_COMMIT || process.env.SOURCE_COMMIT || process.env.RAILWAY_GIT_COMMIT_SHA || ''
```

Merge, redeploy, then:

```bash
curl -s https://localloop.ai/health.json | grep commit
```

Expect a 12-character hash, not `""`. Compare it with the latest commit on
`main` to know what is actually running.

### Step 6: remove the fake rating (code, small)

On the HybridCard homepage fallback card, pass no `rating` and no `ratingCount`.
The stars render hollow and the popover is not shown. Check:

```bash
curl -fsS https://hybridcard.ai/ -o /tmp/hc-home.html \
  && grep -c '128 reviews' /tmp/hc-home.html; grep -cE 'Rated [0-9.]+ out of 5' /tmp/hc-home.html
```

The first command must succeed (it fails loudly on any HTTP error), and both
counts must print `0`: the review count and the "Rated N out of 5" star label
(today the page carries `aria-label="Rated 4.4 out of 5 from 128 reviews"`).
Removing only `ratingCount` and leaving `rating` would pass the first grep and
still paint filled stars, which the second grep catches.

### Step 7: close the open review door (code, owner-gated)

This comes before the Facebook post on purpose: the moment the post is live,
anyone can hit the API. Fix section 3.6 first. Smallest safe change: one dependency, `require_public_writes`, that returns
403 whenever `LOOPER_PUBLIC_WRITES` is not `true`, attached to exactly five
route decorators (for example
`@router.post("/reviews", dependencies=[Depends(require_public_writes)])`):
the three public writes (`POST /api/reviews`, `POST /api/onboard`, `POST
/api/pins`) and the two profile reads (`GET /api/users/{id}`, `GET
/api/code/{code}`). Attach it per route, not on the `APIRouter` objects: those
routers also hold the intentionally public `GET /api/reviews/{business_id}`,
`GET /api/pins` and `GET /api/tourist-info`, which must keep working. It must be
a dependency, not a check inside the handler: FastAPI resolves dependencies
before it validates the body, so the guard fires even on an empty request. Also
never read `verified_visit` from the body. Search, discover, businesses,
reviews-by-business, pins-by-area, tourist info and the HMAC-signed bridge
ingest endpoints stay open. This is an auth-adjacent change
to a live API, so say yes before it is built.

Check after deploy with empty bodies. Because the bodies are empty, nothing can
ever be written: with the guard live you get `403`; without it you get `422`
from validation and the database is untouched.

```bash
for path in reviews onboard pins; do
  curl -s -o /dev/null -w "$path %{http_code}\n" -X POST "https://api.localloop.ai/api/$path" \
    -H "Content-Type: application/json" -d '{}'
done
curl -s -o /dev/null -w "users %{http_code}\n" https://api.localloop.ai/api/users/1
curl -s -o /dev/null -w "code %{http_code}\n" https://api.localloop.ai/api/code/123456
```

Expect `403` on all five lines. A `422` on any POST line means the guard is not
live for that route, and a `200` or `404` on a GET line means the same. Either
way nothing was created, so the check is safe to repeat. Then prove the public
reads survived:

```bash
curl -s -o /dev/null -w "reviews-by-business %{http_code}\n" https://api.localloop.ai/api/reviews/3
curl -s -o /dev/null -w "pins-by-area %{http_code}\n" "https://api.localloop.ai/api/pins?lat=-33.8908&lng=151.2748&radius=5000"
```

Expect `200` on both. A `403` here means the guard landed on the whole router
and broke a public read.

### Step 8: two real options before any public traffic (content + one code fix)

Nothing goes to the group until this passes. Two things must be true: the
"hairdresser" matching fix from section 3.16 is deployed, and a second real
hairdresser or barber holds a HybridCard, so the answer can offer two options as
the anti-bias rule requires. Onboarding one
local salon is itself a good test of the card funnel. Verify:

```bash
curl -fsS "https://api.localloop.ai/api/search?q=hairdresser&lat=-33.8908&lng=151.2748&radius_km=1.5" -o /tmp/hair.json \
  && grep -oE '"name":"[^"]*"|"card_url":(null|"[^"]*")' /tmp/hair.json | paste - -
```

Expect two or more lines, each with a `card_url` on a `hybridcard.ai` host, and
then open every one of those links:

```bash
curl -fsSI https://aesthete-hair.hybridcard.ai | head -1
```

Expect `HTTP/2 200` for each. A count of two is not enough on its own: a
business with no card link shows no "View card" action in the dock, so the
loop cannot complete on it. This probe copies what the dock really sends: the
spoken word itself as `q`, and the dock's default 1.5 km radius around the
map's current centre, which is the viewport, not the phone's GPS
(`runSearch()` uses `cmd.coords || mapCenter()` in
`web/jarvis/looper-jarvis.js`). On first load that centre is the site's default
Bondi Beach view (`DEFAULT_PLAYGROUND` in LocalLoop `assets/js/main-map.js`),
which is what the coordinates above approximate. Testers must ask before
panning the map, or both businesses must sit within 1.5 km of wherever they
have panned to. Note that today this returns `0` even for Aesthete because of
the matching bug in section 3.16.

### Step 9: open the free funnel and watch ten strangers (Facebook admin, no code)

1. Pin a welcome post that names the one flow step 8 verified, word for word:
   "Say hi to Looper. Open localloop.ai on your phone, tap the face, and say
   'find me a hairdresser'." Link to `https://localloop.ai/`. Do not write "ask
   for what you need": the brain still answers nothing for cafés and most other
   categories (section 3.2), so an open invitation sends people straight into
   an empty result and those visits cannot count toward the hairdresser
   completion test. Widen the wording only when other categories also pass the
   step 8 probe. Do this only after step 7's checks and step 8's probe both
   pass.
2. Leave the membership questions as they are for now. Do not ask for an email
   yet: with Layer 2 declined and no first-party join page built, an email typed
   into a membership answer vanishes at approval and nothing can deliver the card
   it promised. Add the email ask only when `join.localloop.ai` (F7.1 to F7.3)
   exists to capture it with consent.
3. Record in `.SEED/decisions.md`: Layer 2 (extension capture) declined for now.

**Measuring it.** `analytics.js` records `path` and the referrer on every
`page_view`, but not the query string, so a `?src=` tag would be lost. Facebook
links arrive with a referrer such as `l.facebook.com` or `lm.facebook.com`, so
count those. In the Supabase SQL editor:

```sql
select count(*) as from_facebook
from public.analytics_events
where event = 'page_view' and props->>'ref' ilike '%facebook%';
```

Caveat: the Facebook in-app browser sometimes sends no referrer, so this is a
floor, not an exact count. Recording `location.search` in `analytics.js` is a
one-line LocalLoop change if you want exact `?src=` attribution later.

**Watching them.** Ask five members to try it on their own phones while you watch. Write down
every place they got stuck. Fix the blockers, then run a second round of five.
The success rule needs ten completions, so do not evaluate it after the first
five. That list of stuck points is the real backlog.

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
- HMAC receivers with test matrices on both sides. Tests assert that discount,
  source and `rank_boost` never enter the ordering. They do not cover the order
  of the permitted inputs: `search.py` sorts by text relevance (category, name,
  suburb, description match) before review count and proximity, so a business
  that matches the category word can sit above one with more reviews. That is
  ordinary search behaviour, not pay-to-rank, but AGENTS.md rule 1 reads as
  reviews, recency and proximity only. Section 4, item 7.
- HybridCard's security chokepoints (`toPublic`, 404-not-403, atomic wallet,
  BYOK vault, SSRF guard) are genuinely good.
- Secret scanning in CI in two repos. Kill switches fail closed.
- The Jarvis voice stack is fully embedded in the live page. It only needs step 1.

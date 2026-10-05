# Worker deploy and rollback runbook (`looper-api-proxy`)

The Cloudflare Worker in `workers/looper-api-proxy` serves `api.localloop.ai`.
It forwards every request to the Looper API (`ORIGIN` in `wrangler.toml`).
This runbook covers the one open deploy from looper#20: shipping the
`X-Request-ID` change from looper#17.

**Who runs it:** the owner (Bill) or devops, in an approved change window.
Agents never deploy (`AGENTS.md` rule 5, hot zone: deploys).

**Risk:** low. The new code only adds a missing `X-Request-ID` header (taken
from `cf-ray`) before forwarding. It does not change CORS, caching, routes,
bodies or the bridge signature headers. Rollback takes one command and under
a minute.

Commands below were checked on 2026-10-02 with wrangler 4.146.0. The
"Expected" blocks show the parts that matter. Ids, times and ray values will
be different on your machine.

## 0. Before the window (5 min, changes nothing)

Run everything from the repo root, on an up-to-date `main`:

```bash
git checkout main && git pull
cd workers/looper-api-proxy
node test/index.test.mjs
```

Expected (last line):

```
16 passed, 0 failed
```

Check that you're logged in to the right Cloudflare account:

```bash
npx wrangler whoami
```

Expected: your email, plus an account table that includes the account that
owns the `localloop.ai` zone. If it says "You are not authenticated", run
`npx wrangler login` and try again.

Build without deploying:

```bash
npx wrangler deploy --dry-run
```

Expected:

```
Total Upload: 1.99 KiB / gzip: 0.88 KiB
Your Worker has access to the following bindings:
Binding                                                      Resource
env.ORIGIN ("http://looper-api.167.86.79.151.sslip...")      Environment Variable

--dry-run: exiting now.
```

If `ORIGIN` isn't the Coolify origin you expect, **stop**. Changing it is a
hosting change and needs its own sign-off.

## 1. Write down the current version (your rollback target)

```bash
npx wrangler deployments list
```

Expected: up to 10 deployments, oldest first. The **last** one is live, and
its version has `(100%)` in front of the id:

```
Created:     2026-…
Author:      …
Source:      …
Version(s):  (100%) 1a2b3c4d-…
```

Copy that version id somewhere. You'll need it for rollback if `wrangler
rollback` can't work out the previous version by itself.

Save the "before" headers for the PR or issue:

```bash
curl -s -i -H 'X-Request-ID: e6-deploy-check-001' https://api.localloop.ai/health | grep -i -E '^HTTP|x-request-id|cf-ray'
```

Expected **before** (2026-10-02): `HTTP/2 200` and a `cf-ray` line, with **no**
`x-request-id` line. The live Looper API image doesn't include looper#17 yet,
so nothing echoes the id.

## 2. Deploy

```bash
npx wrangler deploy --message "looper#17 X-Request-ID from cf-ray"
```

Expected: an upload summary, the route `api.localloop.ai/*`, and as the last
line:

```
Current Version ID: <new id>
```

Copy the new id.

## 3. Check it (2 min)

1. Health:

   ```bash
   curl -s https://api.localloop.ai/health
   ```

   Expected: `{"status":"healthy","organization_identity":"/api/identity/health"}`

2. CORS works exactly as before. This line must print `access-control-allow-origin: https://localloop.ai`:

   ```bash
   curl -s -i -X OPTIONS -H 'Origin: https://localloop.ai' -H 'Access-Control-Request-Method: GET' 'https://api.localloop.ai/api/search?q=cafe' | grep -i -E '^HTTP|access-control-allow-origin'
   ```

   A foreign origin is still refused. This must print `400`:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X OPTIONS -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: GET' 'https://api.localloop.ai/api/search?q=cafe'
   ```

3. The map still answers. Open https://localloop.ai, ask Looper for "cafe in
   Bondi", and check you get several results.

4. The new version is live:

   ```bash
   npx wrangler deployments list
   ```

   The last entry must show `(100%) <new id>` with the message you used.

5. Request id end to end. This **only works once the Looper API image with
   looper#17 is deployed on Coolify** (a separate change). Until then no
   `x-request-id` line is the expected result, not a Worker failure:

   ```bash
   curl -s -i -H 'X-Request-ID: e6-deploy-check-001' https://api.localloop.ai/health | grep -i x-request-id
   curl -s -i https://api.localloop.ai/health | grep -i -E 'x-request-id|cf-ray'
   ```

   Expected after both deploys: the first prints
   `x-request-id: e6-deploy-check-001`. The second prints an `x-request-id`
   equal to the `cf-ray` value on the next line (for example
   `a442cebacea23fcd-SYD`).

If checks 1–4 fail, roll back (section 4) right away and note what you saw on
looper#20.

## 4. Rollback (under 1 minute)

```bash
cd workers/looper-api-proxy
npx wrangler rollback --message "rollback looper#17"
```

It prints the live deployment and the version it will return to (the
previous one that was at 100%), then asks
`Are you sure you want to deploy this Worker Version to 100% of traffic?`.
Type `y`. Expected:

```
Worker Version <old id> has been deployed to 100% of traffic.
```

If it says `Could not find stable Worker Version to rollback to`, use the id
you wrote down in section 1:

```bash
npx wrangler rollback <old id> --message "rollback looper#17"
```

Then repeat checks 1–3 from section 3. The Worker stores no data (no KV, D1
or Durable Objects), so there is nothing to repair.

Last resort if wrangler won't work: Cloudflare dashboard → Workers & Pages →
`looper-api` → Deployments → pick the previous version → Deploy.

## 5. Afterwards

Post on looper#20: the date and time, the new version id, and what checks
1–4 printed (headers only, no response bodies). Then tick "Deploy the updated
`looper-api-proxy` Worker". Check 5 gets ticked once the backend image is
deployed too.

## Never do this in this window

- Don't edit `ORIGIN`, `[[routes]]` or DNS. Those are hosting changes with
  their own sign-off.
- Don't run `wrangler secret …`. This Worker has no secrets.
- Don't commit `workers/looper-api-proxy/.wrangler/`. It's local cache and
  holds your account id. `.gitignore` covers it.

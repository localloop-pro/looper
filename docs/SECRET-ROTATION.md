# Rotating the bridge secret (`HYBRIDCARD_INGEST_SECRET`)

**Who:** the owner (Bill) only. This touches production secrets on Coolify
and hybridcard.ai, so it is a hot zone and agents never do it.

**Why now (looper#48):** commit `eaa1fbd` put a real value of this secret
into `plans/evidence/F9.1/README.md`. The current file is clean, but the old
commit is still in public history, and forks and clones keep it. Anyone with
that value can sign deal and card events that the looper receivers will
accept. Rewriting history does not take the value back. Rotating it does.

## What rotation means here (read this first)

- The sender (hybridcard.ai `src/lib/bridge/outbox.ts`) signs every event
  with **one** secret, `HYBRIDCARD_INGEST_SECRET`, and always sends key id
  `hc-1`.
- The receiver (`backend/services/bridge_hmac.py::load_keys`) gives **every**
  id in `HYBRIDCARD_KEY_IDS` that same single secret.
- So **adding `hc-2` to `HYBRIDCARD_KEY_IDS` rotates nothing.** The leaked
  value would still verify under every id (pinned by
  `backend/tests/test_secret_rotation.py::test_new_key_id_alone_does_not_rotate`).
  You have to change the secret value itself, on both sides.
- During the few minutes when only one side has the new value, events get
  `401`. That's fine: the sender's outbox retries with backoff
  (30 s, 1 min, 2 min, 4 min, 8 min, 16 min; 6 tries, about 30 minutes in
  total). Finish both sides within about 15 minutes and nothing is lost.

## Steps (about 10 minutes)

1. Make a new value on your own machine. Don't paste it into any repo
   file, issue, PR or chat:

   ```bash
   openssl rand -hex 32
   ```

   Save it in your password manager.

2. **looper-api (Coolify):** open the looper-api app, then Environment
   Variables. Set `HYBRIDCARD_INGEST_SECRET` to the new value and leave
   `HYBRIDCARD_KEY_IDS=hc-1` as it is. Save, then **Restart** (the receiver
   reads the env at startup).

3. **hybridcard.ai (Coolify):** open the hybridcard app, then Environment
   Variables. Set `HYBRIDCARD_INGEST_SECRET` to the same new value. Save,
   then **Restart**.

4. Update your local copies that hold the old value (`secrets/`, any
   gitignored `.env.local`). Never commit them.

## Check it worked

This probe sends a signed empty body `{}`. The receiver checks the
signature **before** it reads the body, so:

- `422` means the signature was accepted. The secret matches, and the empty
  body is rejected, so nothing is written.
- `401` means the signature was rejected.

Run it from the looper repo root after the backend venv is set up
(`cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
`read -s` keeps the values off the screen and out of your shell history.

```bash
cd backend
read -s NEW && export NEW     # paste the NEW value, press Enter
read -s OLD && export OLD     # paste the OLD (leaked) value, press Enter
.venv/bin/python - <<'PY'
import os, httpx
from services import bridge_hmac
url = "https://api.localloop.ai/api/ingest/hybridcard-deal"
for label, secret in (("new", os.environ["NEW"]), ("old", os.environ["OLD"])):
    h = bridge_hmac.sign(b"{}", secret)
    h["Content-Type"] = "application/json"
    r = httpx.post(url, content=b"{}", headers=h, timeout=20)
    print(label, r.status_code)
PY
unset NEW OLD
```

Expected output:

```
new 422
old 401
```

- `old 422`: the looper-api restart in step 2 didn't take, so the leaked
  value still works. Restart it again.
- `new 401`: the value in Coolify isn't the one you pasted.

Last, in hybridcard.ai, edit and save one of your own deals. Its bridge
status should go green (outbox event `sent`, not `failed`), which shows the
sender has the new value too.

## If something goes wrong (rollback)

- Bridge events stay `failed` or pending after both restarts: the two
  values don't match. Copy the value from your password manager into both
  apps again and restart both.
- To roll back, put the previous value back on **both** sides and restart.
  Only do this if you have to: the previous value is the leaked one.
- Events that used up all 6 tries: re-save the deal or card in
  hybridcard.ai and it will be queued again. Receivers are idempotent on
  `eventId`, so duplicates are harmless.

## Optional: history rewrite

Purging `eaa1fbd`'s value needs a force push to `main` (for example
`git filter-repo`), which agents must never do. It's cosmetic once the
value has been rotated, so do it only if you want a clean history.
Never add a gitleaks allowlist entry for that commit.

## Guard against a repeat

`backend/tests/test_secret_rotation.py::test_no_bridge_secret_values_in_tracked_files`
fails the test suite if any tracked file assigns a long hex or base64 value
to `HYBRIDCARD_INGEST_SECRET` or `LOCALLOOP_BRIDGE_SECRET`. On failure it
prints only `file:line`, never the value.

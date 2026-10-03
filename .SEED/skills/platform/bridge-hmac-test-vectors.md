---
name: bridge-hmac-test-vectors
form: function
archetype: platform
home_repo: hybridcard-v2
path: src/lib/bridge/hmac.ts
status: candidate
owner_floor: hybridcard-v2
risk: medium
why: Four implementations of the frozen BRIDGE-CONTRACT-v1 HMAC scheme have no shared proof they agree; one golden vector file tested by all four would.
---

# bridge-hmac-test-vectors (inventory top-5 #4)

One JSON file of golden test vectors for the BRIDGE-CONTRACT-v1 signature
(`X-HC-*` headers, HMAC-SHA256 over `"{ts}.{body}"`), owned by the sender,
that every implementation's tests check against. Inventory row B4
(`docs/skills/INVENTORY.md`, looper#72).

Pinned: looper @ `9becb9c` · map @ `13400a8` · cards @ `7a0e584`

## Evidence

The same scheme in three languages plus a test signer:

- cards (sender) `src/lib/bridge/hmac.ts`: sign cards `src/lib/bridge/hmac.ts:15`,
  verify cards `src/lib/bridge/hmac.ts:27`.
- map gateway: verify map `workers/looper-gateway/src/bridge-hmac.mjs:110`,
  sign map `workers/looper-gateway/src/bridge-hmac.mjs:144`.
- looper receiver: verify looper `backend/services/bridge_hmac.py:29`,
  sign looper `backend/services/bridge_hmac.py:62`.
- looper non-prod check signer: looper `tools/e6_nonprod_check.py:62`.

## Proposed scope

- hybridcard-v2 publishes `bridge-hmac-vectors.json`: rows of
  (test-only secret, key id, timestamp, body) → expected headers, plus
  rows that must fail (stale timestamp, wrong key id, tampered body).
- Each repo adds one test that reads the file and checks its sign and verify.
- **Leave the code alone.** No shared code across runtimes, and no change to
  the contract (it is frozen; receivers adapt to the sender, AGENTS.md rule 3).
- Secrets in the file are fixed test strings, never a real key.

## Shared with

- hybridcard-v2 (home, the sender).
- looper: `backend/services/bridge_hmac.py`, `tools/e6_nonprod_check.py`.
- localloop.pro-main: `workers/looper-gateway/src/bridge-hmac.mjs`.

## Why risk `medium`

Matches inventory row B4 (med: frozen contract, hot zone). Tests only: no
writes, messages, money or LLM calls. But BRIDGE-CONTRACT-v1 is a hot zone,
so the cards owners sign off the vector file before the other floors copy
it, and a vector that disagrees with the live sender is a contract question,
never a reason to change the sender.

# #146 — A cancelled smoke is not a code failure (2026-11-19)

main-red opened #146 for d49c61d, but its `jarvis-smoke` job was cancelled by
`timeout-minutes: 5` while `npx playwright install --with-deps chromium` was
still in its apt step. The smoke never ran. The same `web/` tree passed locally
and the next main push (6af5c7d) was green with no code change.

Read the job annotations before changing code: `exceeded the maximum execution
time` means a time limit, `The operation was canceled` alone means a newer
push replaced the run. Over 30 runs the apt step took 10 s to over 5 min,
while the smoke itself takes under 10 s. The fix for this flake is the protected
workflow (a longer job timeout or a step timeout with one retry), so Bill
decides it. Never weaken the smoke or skip the OS dependencies.

Check it yourself from the repo root:

```bash
gh run view 44513130135 --json jobs --jq '.jobs[] | select(.name=="jarvis-smoke") | .steps[] | "\(.name): \(.conclusion)"'
(cd web/tests && npm ci && npx playwright install chromium && npm run smoke)
```

Expected: the install step reports `cancelled`; the local smoke prints
`errors: none` and both `PASS widget recovery` lines, then exits 0.
Rollback: delete this file; nothing else changed.

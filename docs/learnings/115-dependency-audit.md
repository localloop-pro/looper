# PR 115 — dependency audit recovery (2026-10-26)

## Plan and result

The linked CI job failed at the desktop runtime npm audit; Python auditing
passed. Refresh only the affected DOMPurify lock entry from 3.4.16 to 3.4.17,
within Mermaid's existing dependency range. Keep the seed guard and every CI
gate unchanged. Broad npm audit fix also refreshed unrelated tooling, so retain
only the registry-generated DOMPurify version, URL and integrity fields.

## Local verification

- Clean desktop npm ci; typecheck; production build; 47 desktop tests: pass.
- npm audit --omit=dev --audit-level=high: exit 0, no high/critical findings.
- Backend Python 3.12 pytest: 767 passed, 1 TypeDB skip.
- CI reporting script tests: 15 passed.
- Voice router 183, drift 15, Worker 24: all passed.
- Jarvis Playwright smoke: passed at desktop/mobile widths, no errors.
- Additional Chromium probe using installed Mermaid and DOMPurify 3.4.17:
  normal diagram labels render; hostile diagram event handlers/scripts and
  direct HTML/SVG script, onerror and javascript URL payloads are removed.
- git diff --check: pass. Screenshots skipped: dependency recovery and DOM
  assertions, no visual design change. Docker smoke left to hosted CI.

## Remaining work

Hosted CI on the pushed revision must pass before accepting the CI recovery.
The original failed run remains historical evidence.

Two low-severity audit entries remain (KaTeX plus dependent Mermaid), advisory
GHSA-238p-pmpm-9mq7. npm proposes a Mermaid 12 major upgrade to resolve them;
track that as a separate compatibility/security review rather than silently
expanding this focused critical-patch fix. No audit ignores were added.

## Repeat verification

```sh
cd looper-bot
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm ci --no-audit --no-fund
npm audit --omit=dev --audit-level=high
npm run typecheck
npm run build
npm test
```

Rollback: revert the dependency-recovery commit. No deployment performed.

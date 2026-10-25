# #112 — Bound Electron API reads and keep failures opaque

Issue #112 implements F4.1 offline failure handling and the E6 opaque request
ID contract. Timing instrumentation is the issue's explicit SPEC_GAP extension.
A fetch signal alone cannot guarantee completion: race the entire fetch plus
JSON parsing against a timer, abort and clear the timer in finally. Every call
logs only operation, elapsed milliseconds, status, an allowlisted cache token,
and a fresh capped `lb-` UUID. Never read error bodies or echo rejection text.
Unknown cache headers remain in success timing metadata but cannot enter logs.

Table cells escape markdown delimiters while retaining literal &<> because
React renders text. Links allow HTTPS or loopback HTTP and encode closing
parentheses; the existing Electron openExternal host policy still applies.
Rows and successful tool response shapes retain API order and existing fields.

Verification (2026-10-26):
- `cd looper-bot && ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm ci && npm run typecheck && npm run build && npm test`: passed, 55 tests including 8 new cases.
- `cd backend && .venv/bin/python -m pytest -q`: 760 passed, 1 skipped.
- Both web Node suites, Worker suite (24 cases), and `cd web/tests && npm run smoke`: passed.
- `rg -n 'await response.text\(\)' looper-bot/electron/main.cjs`: only unrelated OpenAI/Exa/image calls remain.
- Playwright preview on reserved port 5369: idle face and artifact panel visible;
  snapshot confirmed the UI. Screenshot attempt captured about:blank and is
  not acceptance evidence. Only console error was missing favicon.ico (404).
  Preview stopped afterward. Browser preview does not exercise Electron IPC.
- Adversarial tests cover ignored abort, stalled JSON, unsafe bases and links,
  markdown cells, raw error exclusion, and privacy-safe logs.

Owner QA pending: launch Electron with `LOOPER_API_BASE=http://localhost:8010`
and the owner's existing OpenAI configuration, ask for lunch in Bondi with API
running (two or more rows), then stop API and repeat. Verify graceful offline
speech, face returns idle within about 11 seconds, and no raw body in Live Log.
No keys were read and no paid voice calls were made here.

Existing npm dependency audit reports 13 vulnerabilities (2 low, 10 high,
1 critical); this scoped extraction changes no dependency or lockfile.
Featured spec/todo/done stores are absent; issue #112, this file, and its PR
track this cycle. F4.1 remains unchecked pending owner voice acceptance.
Next: independent QA and hosted CI; no further feature work in this PR.
Rollback: revert this PR's commit and restart Electron; no data/config change.

## QA round 1 correction

Ken found that ArtifactPanel's link regex ignored the client's backslash
escapes, allowing a forged link in a business name/category to become an
anchor. String-only escaping assertions were insufficient. Extracted the
actual inline React renderer and made it consume escaped delimiters before
recognizing links, preserving literal cell text and generated View card and
Website links. Existing Electron host restrictions are unchanged.

Regression executes that same TSX renderer with actual businessesTable output
and asserts rendered HTML has only the two legitimate anchors, including when
the attacker prefixes backslashes. Typecheck/build and all 56 tests pass.
Playwright rendered the actual ArtifactPanel on port 5369 with forged name and
category: both remain text; only cafe.hybridcard.ai and localloop.ai anchors
exist. Screenshot captured after full streaming completed. Initial probe ran
before streaming finished and was repeated after completion. Preview stopped.
`git fetch origin && git merge origin/main` reported already up to date.
Owner API-on/API-off paid voice and face-state acceptance remains unverified;
no owner secrets were accessed. Next: QA round 2 and hosted checks.

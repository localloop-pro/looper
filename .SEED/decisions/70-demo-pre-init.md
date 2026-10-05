# #70 — ask() before init queues; /demo keeps only the query (2026-10-03)

`LooperJarvis.ask(text)` before `init` no longer touches the UI. It stores the
text (latest wins, because a user who clicks several chips wants the last one),
logs a `console.warn` and returns `null`. When `init` finishes, after
deep links apply, it runs the queued ask exactly once. Hosts should still
disable their own controls until `init` runs, as `demo-map.html` now does.

`GET /demo` redirects to the fixed relative path `/web/jarvis/demo-map.html`
and forwards ONLY `cat`, `q` and `fly` (first value of each, re-encoded).
Every other param, including `api`, is dropped (security requirement on
PR #81). The `category` alias is not forwarded; links to `/demo` use `cat`.

If a deep link has `q` and a chip was clicked before init, the deep link's
`fly`/`cat` still apply, then the chip's search runs last and wins; the deep
link's answer is dropped as stale.

Out of scope: floor 1's diverged copy of `looper-jarvis.js` in
localloop.pro-main (`assets/js/jarvis/`). It is untouched here.

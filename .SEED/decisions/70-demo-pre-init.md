# #70 — ask() before init queues; /demo keeps only the query (2026-10-03)

`LooperJarvis.ask(text)` before `init` no longer touches the UI. It stores the
text (latest wins, because a user who clicks several chips wants the last one),
logs a `console.warn` and returns `null`. When `init` finishes, after
deep links apply, it runs the queued ask exactly once. Hosts should still
disable their own controls until `init` runs, as `demo-map.html` now does.

`GET /demo` redirects to the fixed path `/web/jarvis/demo-map.html` plus
the original query string, verbatim. It never redirects to a URL taken from
input.

Out of scope: floor 1's diverged copy of `looper-jarvis.js` in
localloop.pro-main (`assets/js/jarvis/`). It is untouched here.

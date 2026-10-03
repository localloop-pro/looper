# #70 — Host UI is live before the widget is (2026-10-03)

`demo-map.html` wired its chip buttons at parse time, but `LooperJarvis.init`
only runs on `map.on("load")`. Any chip click in that gap called `ask()` →
`setStatus()` on a dock that did not exist yet and threw. A public API that
the host can reach before `init` must be safe before `init`: `ask()` now keeps
the latest request and runs it once the dock is mounted, and the demo keeps
its chips disabled until then.

Redirects drop the query string unless you carry it on purpose. `/demo` now
appends only `request.url.query` to a fixed path. Input never chooses the
path or host, so a value like `?//evil.example` stays a query on our own page,
and there is no open redirect.

To test "before init", give the harness a switch (`?defer=1` +
`window.__initJarvis`) instead of racing a real map load. Then the smoke test
is deterministic.

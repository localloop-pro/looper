# #70 — Host UI is live before the widget is (2026-10-03)

`demo-map.html` wired its chip buttons at parse time, but `LooperJarvis.init`
only runs on `map.on("load")`. Any chip click in that gap called `ask()` →
`setStatus()` on a dock that did not exist yet and threw. A public API that
the host can reach before `init` must be safe before `init`: `ask()` now keeps
the latest request and runs it once the dock is mounted, and the demo keeps
its chips disabled until then.

Redirects drop the query string unless you carry it on purpose, but
forwarding the whole query is too much: `?api=` (or any future page switch)
would ride along. `/demo` now forwards an allowlist only (`cat`, `q`, `fly`,
first value each), parses it with `parse_qsl` and re-encodes it with
`urlencode`, onto a fixed relative path. Filter on the DECODED key (`%61pi`
is `api`), and re-encode so `%0D%0A` can never split the header.

To test "before init", give the harness a switch (`?defer=1` +
`window.__initJarvis`) instead of racing a real map load. Then the smoke test
is deterministic.

A queued ask and a deep-link `q` both search on init. The `reqSeq` guard
already drops the older answer; the smoke test proves it by making the deep
link's stub answer slower than the queued one.

`parse_qsl` drops blank pairs by default, so `?q=&q=coffee` looked like
`?q=coffee` and the second value won. Parse with `keep_blank_values=True`,
claim the key on its first sighting, then skip it if blank (QA round 2).
Owner checks use GET (`curl -sS -D - -o /dev/null`): `curl -I` sends HEAD,
and a GET-only route answers 405.

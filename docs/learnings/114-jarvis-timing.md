# #114 — Time the Jarvis turn without timing the person

Record client latency at the route, response-header, JSON, panel-render and
speech-call boundaries. Keep only the last 20 records in page memory and expose
a copy through `LooperJarvis.timings()`; an optional `onTiming` host hook must
never be able to break the turn.

The safe record is a fixed ten-field shape: intent, opaque request ID, cache
state, status, five durations and result count. It never stores the transcript,
search term, coordinates, result names or URLs, and it is never logged. Read
`X-Request-ID` and `X-Looper-Cache` from the response headers already exposed by
CORS; adding a request header would create an OPTIONS preflight on every query
and make the measured path slower.

Stale responses record nothing because a newer turn owns the UI. Deep links and
radius reruns have no router phase, so their `route_ms` is zero. Network and
non-2xx failures retain the available hop timings but use `status: "error"`,
which keeps the record shape stable without exposing error text.

Run/verify:

```bash
node web/tests/voice-command-router.test.js
node web/tests/jarvis-sync.test.js
(cd web/tests && npm run smoke)
```

# #153 — A 4xx is a bad request, not "brain offline"; no radius without a distance (2026-11-20)

`web/jarvis/looper-jarvis.js` told users "the Looper brain is offline" for
every failed `/search`, including a 422 the brain had answered. It also
said "I found 2 options within 1.5 kilometres" when no result had a
`distance_km`.

Lessons:
- `api()` already records the HTTP status in `error.meta.status` (`null` for
  a network error or timeout). Branch on it: only network errors, timeouts
  and 5xx are an outage. A 4xx gets "I couldn't read that request" and the
  typed input stays open so the user can rephrase.
- Both search catch handlers now call one `apiFailed()`. Two copies of the
  same error path drift apart.
- A radius claim needs at least one known distance. A row with no
  coordinates (`distance_km: null`) proves nothing about where it is, so
  leave the radius out of the speech.

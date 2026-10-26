# #119 — Bound embedded-widget search (2026-10-26)

Use a fixed 15-second deadline for the entire attempt (location, headers and
JSON body), with AbortController cancellation and finally-based control cleanup.
Promise.race is deliberate: abort alone does not settle a non-cooperative host
fetch/body implementation. Only the winning result reaches rendering, so late
completion cannot overwrite a retry. Ignore duplicate submissions while busy.

Treat HTTP failures, invalid JSON and malformed result envelopes as connection
failures; retain the existing plain-text retry message and result formatting.
No ranking, card URL, backend, Worker or frozen-contract changes.

Issue #119 is the approved scope and current plan. Featured spec/todo/done files
are absent here; use this record and the learning file rather than introducing
an unrelated tracking system. Implementation and local acceptance are complete;
PR review/CI and manager merge remain pending. No deployment is authorized.

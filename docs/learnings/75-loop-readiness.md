# #75 — A count alone cannot prove loop readiness (2026-10-03)

Two search options still fail the loop when either has a localhost, missing or
unreachable card link. Report URL and HEAD checks per business, and fail on
missing evidence rather than inferring success from a healthy API. Keep profile
response bodies out of output, including when a profile leak is detected.

Stub every card HEAD in tests and use a local API: a realistic production-shaped
card URL must never cause a test to contact production. Exercise the actual HTTP
transport separately on loopback to verify methods and redirect handling.

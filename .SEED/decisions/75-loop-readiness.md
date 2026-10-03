# #75 — Read-only HTTP loop readiness (2026-10-03)

Use a standalone standard-library command with the dock's Bondi search defaults.
Accept only 403/404/405 for profile reads and 200 for health/search; malformed
responses and network failures fail closed. Check every returned card, preserving
the API's order. Production readiness requires HTTPS on hybridcard.ai or its
subdomains; this checker does not change the receiver's frozen local URL contract.

Do not follow redirects: card HEAD 2xx/3xx passes the requested status probe,
but a redirected destination is not verified. Unsafe/missing card URLs are
reported with the business name and never fetched. The checker sends no write
methods; existing search GET telemetry is still a server-side effect.

Tests live under backend/tests so the existing backend CI discovery and required
ci dependency include them without editing the protected workflow. Production
probes are owner-only; agents/QA use TestClient with card HEADs stubbed.
No Featured spec/todo/database exists here; issue #75 and its PR track this
cycle. STATUS.md is unchanged; its owner can cite this command after merge.

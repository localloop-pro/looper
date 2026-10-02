# LEARNINGS.md — one short lesson per merged PR

- looper#27: guard unauthenticated writes with a per-route FastAPI dependency
  (`dependencies=[Depends(...)]`) so an empty body gets 403 instead of 422, and
  delete leaky reads outright rather than putting them behind the same flag.
  Also: never name a zsh loop variable `path` — it is tied to `$PATH`.
- looper#29: substring search misses compound words ("hairdresser" is not
  inside "Aesthete Hair"). Fix it with a small explicit synonym table that only
  adds word-start alternatives and scores each query word once, never with a
  blanket "contains" rule (that lets "carpet cleaner" hit "Car Wash").
  The voice router must send the user's own word, not a padded list of
  synonyms: a padded bare "hair" made a spoken query looser than the same
  typed one. Test what the router sends against /api/search too.
- looper#32: CI uses one final `ci` job with `if: always()` that fails unless
  every needed job reports `success`, so branch protection needs only one
  required check and a skipped or cancelled job can't pass as green. Check
  action runtimes before copying a workflow: `gitleaks-action@v2` runs on
  Node 20, which GitHub removed from hosted runners on 2026-09-16, so use `@v3`.
- looper#28: a per-IP limit is only as good as the IP header, and that header
  is only trustworthy when the origin can't be reached around the proxy. Lock
  the origin with a shared key the proxy *replaces* (never appends), check it
  with `hmac.compare_digest`, and place the guard outside the rate limiter but
  inside CORS/correlation so a 403 still reads well in the browser and logs.
  Never return `String(err)` from a proxy: it can name the origin.

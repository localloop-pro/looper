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
- looper#37: the API returns user-echoed text (`message` repeats `q`) as plain
  JSON. Escaping is the renderer's job: escaping in the API would show `&amp;`
  in Jarvis and speak it aloud. Pin it with a test that fails on `&amp;`, and
  when a sink lives in another repo, file an issue for every copy of it.

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
- looper#38: Looper sends card_url (the sender's public_card_url, any host,
  as sent) as the only card link and never a slug. When a consumer reads a
  field we don't send, fix the consumer (localloop.pro-main#333) instead of
  adding a column to live data without the owner's OK.

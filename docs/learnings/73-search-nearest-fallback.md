# #73 — An empty answer should say how far the nearest match is (2026-10-03)

The Jarvis dock searches 1.5 km around the map centre and the production
brain is sparse, so most voice questions came back `[]` even when a match
was 2-4 km away. The empty message also invited people to "add one", but
POST reviews/onboard/pins return 403 unless `LOOPER_PUBLIC_WRITES=true`
(#27), so the invitation went nowhere.

Lessons:
- In `/api/search` the radius filter runs in Python on rows that already
  matched the text, so a widened pass is a second filter over the same
  list, not a second SQL query. Compute distance before the per-row review
  queries, so out-of-range rows cost nothing.
- User-facing copy is a claim. "Most reviewed first" was false: the sort is
  relevance, then review_count, then distance. Keep the message describing
  what `results.sort` actually does (`ORDER_TEXT` in `routes/search.py`), and
  never point users at an action a flag has switched off.
- "Nearest" is the smallest `distance_km` among the returned results, not
  the first result, because the first result is the best text match.
- The fallback must not change the order: the anti-bias test for it uses a
  closer business with a 90% deal, a HybridCard source and `rank_boost=true`,
  and checks that the reviewed one still ranks first.

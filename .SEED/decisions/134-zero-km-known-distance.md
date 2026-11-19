# 134 — 0.0 km is a known distance (2026-11-19)

Issue: looper#134 "Treat 0.0 km as a known distance in search and map pins".

- In `/api/search` and `/api/pins`, distance is known whenever it is not
  `None`. A rounded distance of `0.0` (0 to 50 m) is reported as `0.0`, not
  `null`.
- The proximity sort key uses `999` only for a genuinely unknown distance, so
  a coincident result ranks ahead of a farther one with the same relevance and
  review count.
- Ranking inputs are unchanged (relevance, review count, proximity). `rank_boost`
  stays `false`. Response shapes and status codes are unchanged.

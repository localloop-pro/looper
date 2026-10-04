# #107 — A read route must say "no such thing" apart from "nothing yet" (2026-10-04)

`GET /api/reviews/{business_id}` answered `200 + []` for an id that does not
exist, so a caller could not tell a typo from a business with no reviews. It
now returns `404 Business not found`, the same answer `POST /api/reviews`
already gave, and `limit` is bounded to 1–50 like `/api/discover`.

Before changing a public status code, grep every caller in all three repos
(`grep -rn "api/reviews"` in looper, localloop.pro-main and hybridcard-v2).
Here only tests and docs used the route, so the change was safe. Check the
middleware too: `edge_boundary.py` adds `no-store` to every `/api/reviews/`
response whatever its status, so the 404 is never cached.

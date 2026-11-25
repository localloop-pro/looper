# 213 — Pin the clock in rate-limit tests; keep the fixed-window limiter

**Context.** `test_rate_limit_429_with_retry_after_and_cors` failed once in CI
(`assert 200 == 429`). `RateLimiter.hit` counts per `int(time.time() // 60)`
(fixed one-minute window), so four requests straddling a wall-clock minute
boundary land in two windows and none is limited.

**Decision.** Fix the test, not the limiter: `test_edge_read_boundary.py` pins
`edge_boundary.time.time` mid-window, and
`test_rate_limit_window_resets_on_next_minute` documents the reset. Production
behaviour is unchanged, as the issue requires unless the flake is a real bug.

**Not decided here.** A fixed window lets a client send up to 2x the limit
across a boundary. Moving to a sliding window would be a behaviour change in
`services/edge_boundary.py` (protected, and the read rate limit stays dark
until the E1 ADR is accepted), so it needs the owner's call in its own issue.

**Reproduce the flake.** With the clock at 59.9 send 2 requests (limit 3), set
it to 60.1, send 2 more: the 4th returns 200, not 429. Rollback: revert the PR.

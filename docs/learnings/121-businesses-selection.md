# #121 — Limit after eligibility and ranking

A SQL limit before Python radius filtering can return no matches even when
nearby rows exist later. Sorting the already limited rows also misses reviewed
options. Disposable fixtures reproduced zero results at both limits 1 and 50
with a distant prefix; the corrected endpoint returns 1 and 50 eligible rows.

Use explicit None checks for optional coordinates and distances. Valid latitude,
longitude and distance may all be zero. Keep full precision until presentation,
and use ID for deterministic exact ties. Missing-coordinate rows retain their
previous inclusion policy.

Query-budget proof: 1,101 eligible rows use four statements at limits 1 and 50
(one candidate read plus three review-stat batches), with no per-row reads.
The intentional snapshot refresh changes only two /api/businesses cases;
/api/search and /api/discover snapshots are unchanged.

Verify from the repository root:

```sh
cd backend
.venv/bin/python -m pytest -q tests/test_businesses_selection.py tests/test_coordinate_bounds.py tests/test_cross_repo_contracts.py tests/test_search_sql_budget.py tests/test_read_path_identity.py tests/test_search_antibias.py
```

Independent static adversarial review found no blocking issue; runtime and CI
results are recorded in the PR. UI code is unchanged, so no screenshot is
needed. Electron's synthetic list test preserves selected order, count and
zero distance. Production and deployment remain unverified and owner-gated.

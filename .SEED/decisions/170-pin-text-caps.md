# 170 — Length caps on public POST /api/pins text

**Decision:** `MapPinRequest` (`backend/schemas.py`) caps `title` at 200,
`description` at 2000 and `category` at 100 characters. Longer values get a
422 and nothing is stored.

**Why:** `POST /api/pins` is a public write and `GET /api/pins` returns every
pin to anyone, so unbounded text lets one caller bloat storage and the list
response. The search query got the same kind of cap at the public boundary
(#138). 2000 and 100 match the existing review-text and
`interest_category` bounds in `schemas.py`; 200 is a short headline length.
`pin_type` is left alone (product decision, not part of this issue).

**Verify (copy-paste):**

```bash
cd backend && mkdir -p data && python3 -m pytest -q tests/test_map_pins_text_caps.py
```

Expect 6 passed (3 over-limit give 422, 3 at-limit give 200).

**Rollback:** revert the PR for #170; the caps are only the three
`max_length` arguments in `MapPinRequest`.

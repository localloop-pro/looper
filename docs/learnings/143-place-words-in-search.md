# #143 — Place words say where, not what (2026-11-20)

"vet in Bondi Junction" listed Bondi Plumbing Co, Bondi Wholefoods and Bondi
Junction Medical next to the two vets. `/api/search` matched every non-stopword
against business names, and most local names start with the suburb, so
"bondi" and "junction" made almost every business a "match".

Now, when a question names a thing *and* a known suburb (`SUBURB_COORDS` in
`backend/routes/discover.py`), only the thing decides which businesses match.
The place still adds the usual suburb score, but only against the suburb
field, never the name. A place-only question ("Bondi") behaves as before.
Ranking inputs are unchanged (text relevance, review count, distance); the
read-path snapshot kept every result and its order, and only `total_results`
dropped for four place questions (the padding is no longer counted).

Check it yourself from the repo root:

```bash
cd backend && .venv/bin/python -m pytest -q tests/test_search_place_words.py tests/test_read_path_identity.py && cd ..
```

Expected: `8 passed`. On the demo seed, "vet in Bondi Junction" returns only
Bondi Vet and Rose Bay Vet.
Rollback: `git revert` this PR's merge commit.

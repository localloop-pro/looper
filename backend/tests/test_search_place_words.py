"""looper#143: place words in the question must not match business names.

"vet in Bondi Junction" listed Bondi Plumbing Co and Bondi Wholefoods
because "bondi" and "junction" were matched against every business name.
The rows below mirror the demo seed (backend/seed.py) that the UI review used.
"""
import pytest

from models import Business

ROWS = [
    ("Bondi Wholefoods", "café", "Bondi", -33.8908, 151.2748),
    ("Gertrude & Alice", "café", "Bondi", -33.8893, 151.2735),
    ("Bondi Junction Medical", "doctor", "Bondi", -33.8916, 151.2498),
    ("Bondi Vet", "vet", "Bondi", -33.8930, 151.2495),
    ("Rose Bay Vet", "vet", "Rose Bay", -33.8720, 151.2650),
    ("Bondi Plumbing Co", "plumber", "Bondi", -33.8915, 151.2650),
    ("Bondi Beach Dental", "dentist", "Bondi", -33.8895, 151.2750),
    ("Speedo's Café", "café", "Bondi", -33.8870, 151.2780),
]


@pytest.fixture()
def seeded(db):
    for name, category, suburb, lat, lng in ROWS:
        db.add(Business(name=name, category=category, suburb=suburb,
                        lat=lat, lng=lng, source="manual"))
    db.commit()
    return db


def _categories(client, q):
    resp = client.get("/api/search", params={"q": q})
    assert resp.status_code == 200
    return [(r["name"], r["category"]) for r in resp.json()["results"]]


@pytest.mark.parametrize("q, wanted", [
    ("vet in Bondi Junction", "vet"),
    ("good café near Bondi Beach", "café"),
])
def test_place_words_do_not_pull_in_other_trades(client, seeded, q, wanted):
    results = _categories(client, q)
    assert results, f"no results for {q!r}"
    others = [r for r in results if r[1] != wanted]
    assert others == [], f"{q!r} listed non-{wanted} businesses: {others}"


def test_place_still_scores_against_suburb(client, seeded):
    # Both vets match "vet"; the one whose suburb is Bondi comes first.
    assert [n for n, _ in _categories(client, "vet in Bondi Junction")] == [
        "Bondi Vet", "Rose Bay Vet"]


def test_place_only_question_still_lists_that_place(client, seeded):
    names = [n for n, _ in _categories(client, "Bondi")]
    assert len(names) >= 2
    assert "Rose Bay Vet" not in names


def test_business_name_with_a_place_in_it_still_found(client, seeded):
    assert _categories(client, "Bondi Plumbing")[0][0] == "Bondi Plumbing Co"

"""Search query normalisation — a small, explicit synonym / compound-word table.

BLIND-SPOTS §3.16 (looper#29): "hair dresser" found Aesthete Hair but
"hairdresser" found nothing, because search matches each query word as a
substring of name / category / suburb / description. This table expands an
everyday word into a few alternatives BEFORE matching.

Rules (keep them when you add an entry):
- Expansion only ADDS alternatives. The user's own word is always kept and
  still matches as a substring, exactly as before.
- Added alternatives must match at the START of a word ("hair" matches
  "Aesthete Hair", never "Chair Hire"). There is deliberately no blanket
  "query word contains a name word" rule: "carpet cleaner" must never match
  "Car Wash".
- One query word = one group. Relevance scores a group once (its best
  alternative), so an expanded word never outweighs an unexpanded one.
- Text match only. Nothing here can see discount, card_url, source, payment
  or rank_boost (anti-bias, AGENTS.md rule 1).

Keys and values are accent-folded lowercase (see models.fold_accents).
web/jarvis/voice-command-router.js mirrors these words so typed and spoken
queries agree — change both together.
"""
import re

# word -> extra alternatives (justified by the seeded categories in seed.py
# and the live Aesthete Hair card filed under "professional").
EXPANSIONS: dict[str, tuple[str, ...]] = {
    # hair & beauty (seed category "hairdresser"; live card "Aesthete Hair")
    "hairdresser": ("hair", "salon"),
    "hairdressers": ("hair", "salon", "hairdresser"),
    "hairdressing": ("hair", "salon", "hairdresser"),
    "salon": ("hair", "hairdresser"),
    "salons": ("hair", "hairdresser", "salon"),
    "barber": ("hair", "barber"),
    "barbers": ("hair", "barber"),
    "barbershop": ("hair", "barber"),
    "haircut": ("hair", "barber", "salon"),
    "haircuts": ("hair", "barber", "salon"),
    # food (seed category "café"; accents are folded before lookup)
    "cafe": ("coffee", "cafe"),
    "cafes": ("coffee", "cafe"),
    "coffee": ("cafe",),
    # health (seed categories doctor, dentist, pharmacy, physiotherapist, fitness)
    "gp": ("doctor", "medical"),
    "gps": ("doctor", "medical"),
    "doctors": ("doctor", "medical"),
    "dental": ("dentist",),
    "dentists": ("dentist", "dental"),
    "chemist": ("pharmacy",),
    "chemists": ("pharmacy",),
    "physio": ("physiotherapist",),
    "gym": ("fitness",),
    "gyms": ("fitness",),
    # trades & pets (seed categories plumber, electrician, vet)
    "plumbers": ("plumber", "plumbing"),
    "electricians": ("electrician", "electrical"),
    "sparky": ("electrician", "electrical"),
    "sparkie": ("electrician", "electrical"),
    "sparkies": ("electrician", "electrical"),
    "vets": ("vet",),
    "veterinarian": ("vet",),
}

# Two spoken/typed words that mean one compound word. The originals stay in
# the group; the compound's alternatives are added.
COMPOUNDS: dict[tuple[str, str], str] = {
    ("hair", "dresser"): "hairdresser",
    ("hair", "dressers"): "hairdressers",
    ("hair", "salon"): "salon",
    ("barber", "shop"): "barbershop",
}


class Term:
    """One alternative: the user's own word matches anywhere (substring, the
    pre-#29 behaviour); an added alternative must start a word."""

    __slots__ = ("text", "original", "_re")

    def __init__(self, text: str, original: bool):
        self.text = text
        self.original = original
        self._re = None if original else re.compile(r"(?<![a-z0-9])" + re.escape(text))

    def matches(self, haystack: str | None) -> bool:
        if not haystack:
            return False
        if self.original:
            return self.text in haystack
        return self._re.search(haystack) is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Term({self.text!r}, original={self.original})"


def expand(tokens: list[str]) -> list[list[Term]]:
    """Turn folded query tokens into match groups (one group per query word,
    or per recognised two-word compound). Order and originals preserved."""
    groups: list[list[Term]] = []
    i = 0
    while i < len(tokens):
        pair = tuple(tokens[i:i + 2])
        if len(pair) == 2 and pair in COMPOUNDS:
            originals = list(pair)
            key = COMPOUNDS[pair]
            i += 2
        else:
            originals = [tokens[i]]
            key = tokens[i]
            i += 1
        group = [Term(w, original=True) for w in originals]
        seen = set(originals)
        for alt in (key, *EXPANSIONS.get(key, ())):
            if alt not in seen:
                seen.add(alt)
                group.append(Term(alt, original=False))
        groups.append(group)
    return groups


def group_matches(group: list[Term], haystack: str | None) -> bool:
    return any(t.matches(haystack) for t in group)

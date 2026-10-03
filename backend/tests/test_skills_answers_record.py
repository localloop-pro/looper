"""Owner answers record for the skills registry layout (looper#79).

Only the owner's comment on looper#79 may fill the "Owner answer" column of
`.SEED/decisions/79-skills-registry-answers.md`. These checks keep the record
honest: while it says AWAITING OWNER every answer is `_pending_`; once it says
DECIDED no answer is pending and the owner's comment is linked. They also check
that registry docs which point at an open owner question name one that exists.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECORD = ROOT / ".SEED" / "decisions" / "79-skills-registry-answers.md"
GRILL_ME = ROOT / ".SEED" / "skills" / "GRILL-ME.md"
OWNER_COMMENT = "https://github.com/localloop-pro/looper/issues/79#issuecomment-"


def _answers():
    rows = re.findall(r"^\| ([A-G]) \|.*\| ([^|]+?) \|$", RECORD.read_text(encoding="utf-8"), re.M)
    return dict(rows)


def _status():
    match = re.search(r"^\*\*Status: (AWAITING OWNER|DECIDED \d{4}-\d{2}-\d{2})", RECORD.read_text(encoding="utf-8"), re.M)
    assert match, "record needs a '**Status: AWAITING OWNER' or '**Status: DECIDED <date>' line"
    return match.group(1)


def _open_question_ids():
    section = GRILL_ME.read_text(encoding="utf-8").split("## 3. Open questions", 1)[1]
    return set(re.findall(r"\*\*(Q-[A-G])\.", section))


def test_record_has_one_row_per_question():
    assert sorted(_answers()) == list("ABCDEFG")


def test_answers_match_status():
    answers = _answers()
    if _status() == "AWAITING OWNER":
        assert set(answers.values()) == {"_pending_"}, "answers filled in but status still AWAITING OWNER"
    else:
        assert "_pending_" not in answers.values(), "status DECIDED but an answer is still pending"
        assert OWNER_COMMENT in RECORD.read_text(encoding="utf-8"), "DECIDED needs a link to the owner's comment"


def test_grill_me_lists_every_question():
    assert _open_question_ids() == {f"Q-{q}" for q in "ABCDEFG"}


def test_registry_docs_point_at_open_questions():
    # GRILL-ME §2 numbers its self stress-test Q1..Qn; owner questions are Q-A..Q-G.
    # A pointer to an owner question must use the lettered id.
    open_ids = _open_question_ids()
    for doc in (".SEED/skills/README.md", ".SEED/skills/schema.json"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        refs = re.findall(r"GRILL-ME(?:\.md)? (Q-?[A-Z0-9]+)", text)
        assert refs, f"{doc} should point at the open floors question"
        for ref in refs:
            assert ref in open_ids, f"{doc} points at {ref}, not an open owner question"

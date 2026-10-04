"""Owner answers record for the skills registry layout (looper#79).

Only the owner's comment on looper#79 may fill the "Owner answer" column of
`.SEED/decisions/79-skills-registry-answers.md`. These checks keep the record
honest: while it says AWAITING OWNER every answer and the owner evidence are
`_pending_`; once it says DECIDED no answer is pending and the evidence is the
full link to a numeric comment on looper#79. The table must have exactly one
row for each question A-G. They also check that registry docs which point at an
open owner question name one that exists.
"""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECORD = ROOT / ".SEED" / "decisions" / "79-skills-registry-answers.md"
GRILL_ME = ROOT / ".SEED" / "skills" / "GRILL-ME.md"
QUESTIONS = list("ABCDEFG")
PENDING = "_pending_"
OWNER_COMMENT = re.compile(r"https://github\.com/localloop-pro/looper/issues/79#issuecomment-[0-9]+")

HEADER = ["Q", "Question", "Proposal", "Owner answer"]
# Indented copies still count: Markdown renders a row or paragraph indented by
# up to 3 spaces, so a hidden duplicate must not escape the check.
_STATUS = re.compile(r"^[ \t]*\*\*Status: (AWAITING OWNER|DECIDED \d{4}-\d{2}-\d{2})\b", re.M)
_EVIDENCE = re.compile(r"^[ \t]*\*\*Owner evidence:\*\*(.*)$", re.M)
_SEPARATOR = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")


def _cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def table_problems(text):
    """The record holds exactly one table: header, separator, rows A-G.

    Every line that contains a pipe must belong to that table, wherever it is
    and however it is indented or written (with or without outer pipes), so an
    extra or duplicate row cannot hide. Rows are counted before any filtering.
    Returns (problems, answers).
    """
    lines = text.splitlines()
    piped = [i for i, line in enumerate(lines) if "|" in line]
    if not piped:
        return ["no question table"], []
    if piped != list(range(piped[0], piped[-1] + 1)):
        return ["every line with a '|' must be in one contiguous question table"], []
    after = piped[-1] + 1
    if after < len(lines) and lines[after].strip():
        # A non-blank line right after a table is rendered as another row.
        return ["the question table must be followed by a blank line"], []

    header, separator, *rows = [lines[i] for i in piped]
    problems = []
    if _cells(header) != HEADER:
        problems.append(f"table header must be {HEADER}")
    if not _SEPARATOR.match(separator.strip()):
        problems.append("second table line must be the |---| separator")
    if len(rows) != len(QUESTIONS):
        problems.append(f"table must have exactly {len(QUESTIONS)} question rows; found {len(rows)}")
    ids, answers = [], []
    for row in rows:
        cells = _cells(row)
        ids.append(cells[0])
        if len(cells) != len(HEADER):
            problems.append(f"row {cells[0]!r} must have {len(HEADER)} cells")
        else:
            answers.append(cells[-1])
    if ids != QUESTIONS:
        problems.append(f"question rows must be exactly A-G once each, in order; found {ids}")
    return problems, answers


def record_problems(text):
    """Every reason the record is not a valid AWAITING or DECIDED record."""
    problems, answers = table_problems(text)

    statuses = _STATUS.findall(text)
    if len(statuses) != 1:
        problems.append(f"need exactly one '**Status: AWAITING OWNER' or '**Status: DECIDED <date>' line; found {len(statuses)}")
        return problems
    evidence = [e.strip() for e in _EVIDENCE.findall(text)]
    if len(evidence) != 1:
        problems.append(f"need exactly one '**Owner evidence:**' line; found {len(evidence)}")
        return problems

    if statuses[0] == "AWAITING OWNER":
        if any(a != PENDING for a in answers):
            problems.append("answers filled in but status still AWAITING OWNER")
        if evidence[0] != PENDING:
            problems.append("owner evidence filled in but status still AWAITING OWNER")
    else:
        if any(a in ("", PENDING) for a in answers):
            problems.append("status DECIDED but an answer is still pending or empty")
        if not OWNER_COMMENT.fullmatch(evidence[0]):
            problems.append(f"status DECIDED needs owner evidence = full looper#79 comment URL; got {evidence[0]!r}")
    return problems


def _open_question_ids():
    section = GRILL_ME.read_text(encoding="utf-8").split("## 3. Open questions", 1)[1]
    return set(re.findall(r"\*\*(Q-[A-G])\.", section))


def test_record_is_valid():
    assert record_problems(RECORD.read_text(encoding="utf-8")) == []


def test_grill_me_lists_every_question():
    assert _open_question_ids() == {f"Q-{q}" for q in QUESTIONS}


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


# --- The checker itself, on mutations of the real record ---------------------

# Synthetic id: no real comment is implied to be the owner's answer.
GOOD_URL = "https://github.com/localloop-pro/looper/issues/79#issuecomment-1000000001"
_REAL = RECORD.read_text(encoding="utf-8")
_STATUS_LINE = _STATUS.search(_REAL).group(0)
_FILLED_A = "| A | duplicate | proposal | Registry only |"


def _set_evidence(text, value):
    return _EVIDENCE.sub(lambda _: f"**Owner evidence:** {value}".rstrip(), text, count=1)


def _decided(evidence=GOOD_URL, text=_REAL):
    text = text.replace(_STATUS_LINE, "**Status: DECIDED 2026-10-05", 1)
    text = text.replace(f"| {PENDING} |", "| Proposal OK |")
    return _set_evidence(text, evidence)


def _insert_before_row(text, q, row):
    return re.sub(rf"^(\|\s*{q}\s*\|)", lambda m: f"{row}\n{m.group(1)}", text, count=1, flags=re.M)


def test_checker_accepts_a_complete_decided_record():
    assert record_problems(_decided()) == []


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(_REAL.replace(f"| {PENDING} |", "| Registry only |", 1), id="awaiting-one-answer-filled"),
        pytest.param(_set_evidence(_REAL, GOOD_URL), id="awaiting-evidence-filled"),
        pytest.param(_insert_before_row(_REAL, "A", _FILLED_A), id="awaiting-duplicate-filled-row"),
        pytest.param(_insert_before_row(_decided(), "A", _FILLED_A), id="decided-duplicate-row"),
        pytest.param(re.sub(r"^\| G \|.*\n", "", _REAL, flags=re.M), id="missing-row"),
        pytest.param(_decided().replace("| Proposal OK |", f"| {PENDING} |", 1), id="decided-answer-pending"),
        pytest.param(_EVIDENCE.sub("", _decided(), count=1), id="decided-evidence-missing"),
        pytest.param(_decided(PENDING), id="decided-evidence-pending"),
        pytest.param(_decided("https://github.com/localloop-pro/looper/issues/79#issuecomment-…"), id="decided-evidence-placeholder"),
        pytest.param(_decided("https://github.com/localloop-pro/looper/issues/79#issuecomment-abc"), id="decided-evidence-malformed"),
        pytest.param(_decided("https://github.com/localloop-pro/looper/issues/79"), id="decided-evidence-no-comment"),
        pytest.param(_decided("https://github.com/localloop-pro/looper/issues/80#issuecomment-123"), id="decided-evidence-wrong-issue"),
        pytest.param(_decided("https://github.com/someone/looper/issues/79#issuecomment-123"), id="decided-evidence-wrong-repo"),
        pytest.param(_decided(GOOD_URL + " and more"), id="decided-evidence-trailing-text"),
        pytest.param(_decided() + f"\n**Owner evidence:** {GOOD_URL}\n", id="decided-two-evidence-lines"),
        pytest.param(_decided() + "\n**Status: AWAITING OWNER\n", id="two-status-lines"),
        # QA round 2: duplicates indented like Markdown still renders them, extra ids.
        *[
            pytest.param(_insert_before_row(_REAL, "A", " " * n + _FILLED_A), id=f"awaiting-duplicate-indented-{n}")
            for n in (1, 2, 3, 4)
        ],
        pytest.param(_insert_before_row(_REAL, "A", "\t" + _FILLED_A), id="awaiting-duplicate-tab-indented"),
        pytest.param(_insert_before_row(_decided(), "A", "  " + _FILLED_A), id="decided-duplicate-indented"),
        pytest.param(_insert_before_row(_REAL, "A", "A | duplicate | proposal | Registry only"), id="duplicate-without-outer-pipes"),
        pytest.param(_insert_before_row(_REAL, "A", "| H | extra | proposal | _pending_ |"), id="extra-H-row-inside-table"),
        pytest.param(re.sub(r"^(\| G \|.*)$", r"\1\n| H | extra | proposal | _pending_ |", _REAL, count=1, flags=re.M), id="extra-H-row-at-end"),
        pytest.param(re.sub(r"^(\| G \|.*)$", r"\1\nRegistry only", _REAL, count=1, flags=re.M), id="text-line-glued-to-table"),
        pytest.param(_REAL + "\n| A | duplicate | proposal | Registry only |\n", id="second-table-elsewhere"),
        pytest.param(_REAL.replace("| Q | Question |", "| X | Question |", 1), id="wrong-header"),
        pytest.param(_REAL.replace("| A |", "| A | extra |", 1), id="row-with-five-cells"),
        pytest.param(_decided() + "\n   **Status: AWAITING OWNER\n", id="indented-second-status"),
        pytest.param(_REAL + f"\n  **Owner evidence:** {GOOD_URL}\n", id="indented-second-evidence"),
    ],
)
def test_checker_rejects(text, request):
    # Each case must fail for its own reason, not because another problem masks it.
    case = request.node.callspec.id
    expected = next(reason for prefix, reason in _REASONS.items() if case.startswith(prefix))
    problems = record_problems(text)
    assert any(expected in p for p in problems), (case, problems)


_ROWS = "question rows must be exactly A-G"
_EVIDENCE_URL = "needs owner evidence = full looper#79 comment URL"
_REASONS = {
    "awaiting-one-answer-filled": "answers filled in but status still AWAITING OWNER",
    "awaiting-evidence-filled": "owner evidence filled in",
    "awaiting-duplicate": _ROWS,
    "decided-duplicate": _ROWS,
    "missing-row": _ROWS,
    "duplicate-without-outer-pipes": _ROWS,
    "extra-H-row": _ROWS,
    "decided-answer-pending": "an answer is still pending",
    "decided-evidence-missing": "Owner evidence:**' line; found 0",
    "decided-evidence-": _EVIDENCE_URL,
    "decided-two-evidence-lines": "Owner evidence:**' line; found 2",
    "indented-second-evidence": "Owner evidence:**' line; found 2",
    "two-status-lines": "Status: DECIDED <date>' line; found 2",
    "indented-second-status": "Status: DECIDED <date>' line; found 2",
    "text-line-glued-to-table": "followed by a blank line",
    "second-table-elsewhere": "one contiguous question table",
    "wrong-header": "table header must be",
    "row-with-five-cells": "must have 4 cells",
}

# #79 — An owner question is not an agent's to answer (2026-10-04)

The issue asked Bill seven questions. When an agent picked it up, Bill had not
replied, so the honest result was a draft PR, not answers. Filling the
"Owner answer" column with the proposals would have looked finished and been
wrong. A test now makes that rule mechanical: while the record says AWAITING
OWNER every answer stays `_pending_`; DECIDED needs every row filled and a link
to the owner's comment.

Also: a stacked PR (#105 on #80) can land its parent's files on `main` while
the parent PR stays open, so pointers like "on branch X until PR #80 merges"
go stale silently. And GRILL-ME numbers its self stress-test `Q1..Qn` but the
owner questions `Q-A..Q-G`; README and schema said "Q6" (an MCP question) when
they meant floors (Q-F). The same test now checks every GRILL-ME pointer names
a real owner question.

QA round 1 broke the first guard twice. It searched the whole file for the
comment URL prefix, and the record's own instructions contain that prefix, so
a DECIDED record with no real link passed. It also parsed rows into a dict,
so a filled duplicate row hid behind a later pending one. Fix: an explicit
`**Owner evidence:**` field that must fullmatch a numeric looper#79 comment
URL, exactly seven A-G rows in order, and negative cases built by mutating the
real record so the checker is proven to reject, not just to accept.

QA round 2 hid the duplicate by indenting it 1-3 spaces (Markdown still
renders it as a row) or by adding an H row; the row regex filtered to A-G at
column zero before counting. Fix: parse the table as a block. Every line with
a pipe must sit in the one contiguous table, all its rows are counted before
any filtering, and a non-blank line right after the table is rejected
(Markdown renders it as another row). Widening the evidence match to indented
lines then flagged the record's own instructions, and a negative case can
"pass" for that wrong reason, so each negative case now asserts its specific
problem message.

QA's transition defect: the negative cases were built by mutating the live
record, so filling in the real answers would have changed what they tested.
Checker fixtures are now fixed AWAITING/DECIDED strings inside the test; the
live record gets its own checks (DECIDED, all seven answers, the verified
owner comment) and the README/schema/GRILL-ME are checked against the answers.

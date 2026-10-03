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

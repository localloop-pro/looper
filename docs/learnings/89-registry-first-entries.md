# #89 — A registry entry's file:line is only proof if a script can re-check it (2026-10-03)

The first five registry entries cite 63 file:line locations across three
repos. Checking them by eye is slow and drifts the moment a repo moves on.
Two things made them checkable:

- Each entry pins the commits it read on one `Pinned:` line (repo word, `@`,
  commit in backticks), and every citation names its repo, then the
  backticked `path:line`. A citation without a repo word, or a
  repo without a pin, is ambiguous; the test now fails on the second.
- `tools/check_skill_citations.py` runs `git show <commit>:<path>` in each
  local clone and prints the cited line next to the citation, so a reviewer
  can see that `:39` really is the `db.commit()` that makes a "read" HIGH.

Risk came from the inventory row, not the entry's own reasoning. When one
top-5 item spans rows with different risks (C5 HIGH, C6 low), take the
highest row it still includes and name what was left out (here the signed
ingest phase) so it can't sneak back in.

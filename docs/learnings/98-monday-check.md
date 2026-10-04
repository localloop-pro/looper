# #98 — A status file needs the commands that refresh it (2026-10-03)

STATUS.md said "unverified (owner probe needed)" but never said which probe.
The tools existed on main (`loop_check.py`, `sqlite_backup.py`,
`weekly_numbers.py`), so the fix was a short copy-paste "Monday check" that
ends by naming the exact lines to update.

Copy flags from each script's `--help`, never from memory, and run every
command once against a local preview and a throwaway DB before documenting
it. Don't document a command that depends on an unmerged PR (here `/health`
`commit`, PR #91): add a placeholder line that says what to add once it merges.

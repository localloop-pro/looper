- 2026-10-02 (looper#53): new lessons and decisions go one file per PR in
  `docs/learnings/` and `.SEED/decisions/`, named `<issue>-<short-slug>.md`.
  `docs/LEARNINGS.md` and `.SEED/decisions.md` stay as the entry points and are
  frozen apart from their header note (existing entries not moved). The legacy
  files plus `.SEED/gotchas.md` get `merge=union` as a local-merge safety net.

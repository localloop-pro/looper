# .SEED/decisions/ — one decision per PR, one file each

`.SEED/decisions.md` holds the older decisions; read both.

- One new file per PR, named `<issue>-<short-slug>.md`,
  e.g. `53-one-file-per-entry.md`.
- A few lines, issue reference and date first, same style as
  `.SEED/decisions.md`.
- Never append to `.SEED/decisions.md`: every merge to main moves its end, so
  two open PRs that both append always conflict (looper#53).

- looper#53: an append-only log shared by every PR is a merge-conflict
  generator once two PRs are open and auto-merge is on — each merge moves the
  file's end. Give each PR its own file (`<issue>-<slug>.md`) so changes never
  touch the same lines. `merge=union` in `.gitattributes` only helps a local
  `git merge`; GitHub's mergeability check ignores it.

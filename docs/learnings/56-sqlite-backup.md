- looper#56: back up a live SQLite file with `Connection.backup(pages=-1)` from a
  `file:...?mode=ro` connection, never `cp`. Write to a `.partial` name and
  rename only after `integrity_check` passes, and let retention delete only
  names matching the script's own pattern.

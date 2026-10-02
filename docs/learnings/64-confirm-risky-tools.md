- looper#64: a model that reads untrusted text (search results, pins, records)
  cannot be the one that approves its own desktop actions; a `confirmed: true`
  argument is written by the same model an injected page can steer. Put the
  approval in a native dialog from Electron main, make Deny the default and
  the error path, escape control characters (`\n`, ANSI, bidi overrides) in
  what the dialog shows, and test that the policy list matches the dispatcher
  so a new tool can't skip the gate silently.

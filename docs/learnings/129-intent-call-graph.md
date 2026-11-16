# #129 — Run the documented command in a clean checkout (2026-11-16)

The call-graph generator was first tested with a TypeScript parser installed
in a scratch folder, so `python3 tools/callgraph/build.py` failed for the
owner: a fresh worktree has no `looper-bot/node_modules`. That scratch parser
was also 5.6.3, while the repo pins 6.0.3.

Before documenting a command, run it exactly as written with no extra env
vars (`env -u NODE_PATH ...`). Take tool versions from the lockfile, never
from memory. A script that needs a dependency should fetch the pinned version
itself and fail with one plain sentence, not a traceback.

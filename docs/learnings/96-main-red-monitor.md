# #96 — PR green does not prove main green (2026-10-03)

A telemetry import failure on main was independently patched inside unrelated
PRs because no incident was visible. Treat main CI as its own observable state:
open one actionable issue with failed jobs and the exact run/commit, comment on
repeat failures, and close only after every main gate succeeds.

Keep reporting separate from the required `ci` gate and grant issue writes only
to its main-push job. Pagination and serialized updates prevent the monitor
from opening duplicates; rejecting stale commits avoids old reruns reporting
recovery. Dry runs with fixture issue state test both paths without any API
access. Local unit/CLI evidence is distinct from a real post-merge incident.

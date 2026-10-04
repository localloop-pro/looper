# #86 — Bake the commit into the image, not into a request (2026-10-03)

"Is the fix live?" needs a fact the running process carries, not a guess.
Pass the commit as a Docker build arg (Coolify's `SOURCE_COMMIT`, behind
"Include Source Commit in Build") and expose it as an env var; `/health`
only reads the env. Never run `git` or read `.git` at request time: the image
has no `.git`, and a subprocess per health probe is wasted work.

Declare the `ARG` after the dependency installs, because a changing build
arg invalidates every layer after it. Validate the value as hex before
echoing it on a public endpoint, and keep the health status code unchanged so
existing healthchecks never flip.

Also learned: a green PR can still break `main`. #87's squash-merge lost the
`re`/`EMAIL_RE`/`AU_MOBILE_RE` imports in `services/telemetry.py`, so every
branch from that `main` failed test collection. Run the suite on a fresh
branch from `origin/main` before you assume your own change is the cause.

# looper#20 — Worker deploy runbook, and a glued .gitignore line

- looper#20: one missing newline in `.gitignore` (`training/checkpoints/workers/**/.wrangler/`)
  meant neither path was ignored, so wrangler's account cache got re-committed
  after 3f8c8f2 had untracked it. Check ignore rules with
  `git check-ignore -v <path>`. Don't trust how the file reads.
- Probe the live endpoint before writing a post-deploy check. Production
  echoed no `X-Request-ID`, because the live backend image predates looper#17.
  So the Worker deploy alone can't show the header, and the runbook says so
  rather than calling that a failure.

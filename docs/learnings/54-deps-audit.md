- looper#54: audit only what ships (`pip-audit -r requirements.txt`,
  `npm audit --omit=dev`) and pin the auditor's version. Prove the gate bites
  with a throwaway file pinning an old starlette before trusting a green run.

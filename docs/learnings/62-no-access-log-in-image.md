- looper#62: a logging setting in `main.py` (`uvicorn.run(..., access_log=False)`)
  does not reach production when the image starts uvicorn from the CLI. The
  Dockerfile `CMD` is the real entry point, so it needs its own
  `--no-access-log`, and a test that parses the **last** `CMD` (exec form) so
  the two can't drift apart again.

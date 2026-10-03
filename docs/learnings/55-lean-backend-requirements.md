- looper#55: check what an extra pulls in before dropping a "unused" package —
  `uvicorn[standard]` needs python-dotenv — and check what else runs from the
  same image: the news worker is a scheduled task inside the API container, so
  its deps moved to `tools/requirements.txt` behind a build arg, not deleted.

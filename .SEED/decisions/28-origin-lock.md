- 2026-10-06 (looper#28): the API origin lock is dark until the owner sets
  matching `ORIGIN_KEY` (Worker secret) and `LOOPER_ORIGIN_KEY` (API env).
  `GET /health` remains public. Middleware order, inner to outer, is read
  boundary, origin guard, CORS, correlation: rejected traffic cannot consume
  a rate-limit bucket, while its 403 still carries CORS and request-id headers.
- Production CORS contains HTTPS origins only. Local pages must opt in through
  `LOOPER_DEV_ORIGINS`; browser credentials remain disabled because no caller
  sends them.

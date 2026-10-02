- 2026-10-06 (looper#28): a client-IP header is trustworthy only after callers
  cannot bypass its proxy. The proxy must replace, not append, its private
  origin header; the API compares it in constant time. Proxy errors belong in
  request-id-linked logs, never response bodies where origin details can leak.

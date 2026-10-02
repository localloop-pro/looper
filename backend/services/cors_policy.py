"""CORS allowlist (looper#28).

Production is the https hosts that embed the Jarvis dock or Looper widget.
Local dev hosts are allowed only when listed in `LOOPER_DEV_ORIGINS`
(comma-separated, e.g. `http://localhost:5173,http://localhost:3000`).

No browser caller sends cookies or auth (web/ uses plain fetch or
`credentials: 'omit'`; HybridCard and looper-bot call server-side), so
`allow_credentials` is False.
"""
from __future__ import annotations

import os

# localloop.ai serves the map (Jarvis dock calls api.localloop.ai from the
# browser); hybridcard.ai embeds the read-only search widget.
PRODUCTION_ORIGINS = (
    "https://localloop.ai",
    "https://www.localloop.ai",
    "https://localloop.pro",
    "https://www.localloop.pro",
    "https://explorer.localloop.ai",
    "https://hybridcard.ai",
    "https://www.hybridcard.ai",
)


def dev_origins() -> list[str]:
    raw = os.getenv("LOOPER_DEV_ORIGINS") or ""
    out = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/")
        # "*" would open every site; ignore it rather than widen the list.
        if origin and origin != "*" and origin not in out:
            out.append(origin)
    return out


def cors_options() -> dict:
    return {
        "allow_origins": list(PRODUCTION_ORIGINS) + dev_origins(),
        "allow_credentials": False,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Request-ID", "X-Looper-Cache", "Retry-After"],
    }

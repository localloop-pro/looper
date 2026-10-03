# #93 — Demo hint lives bottom-left, lifted above the map controls (2026-10-03)

The `/demo` help hint stays bottom-left, raised above the MapLibre
NavigationControl (`bottom:112px`), rather than going under the topbar. The
topbar's chips wrap to 2–3 rows on phones, so its height changes, while the
control stack's height is fixed. Bottom-right belongs to the Jarvis dock and
the attribution. On ≤480px the hint starts collapsed behind a `? Tips` button.
The localhost:8000 line shows only when `apiBase` would fall back to it.
Only `demo-map.html` changed. The map init, chip handlers and
`looper-jarvis.js` are untouched (PRs #81 and #85).
Rollback: revert the #93 commit; no data or config involved.

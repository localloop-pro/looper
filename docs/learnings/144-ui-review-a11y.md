# #144 — MapLibre overwrites a marker's aria-label in addTo() (2026-11-19)

The UI review found every Jarvis result pin announced as "Map marker". Setting
`aria-label` on the element before `new Marker({element})` does not help:
MapLibre 4.7.1 calls `setAttribute("aria-label", "Map marker")` inside
`addTo()`. Set the business name *after* `addTo()`.

Same review: clickable `<div>`s are invisible to Tab. Make the visible name a
real `<button>`, so you don't need `role`/`tabindex`/key handlers and the
card's existing click handler still runs. A fixed panel with
`width:min(340px, 100vw - 36px)` plus padding spills off a 375px phone
unless it uses `box-sizing:border-box`. Measure overlaps with element boxes,
not screenshots.

Run/verify (beginner):

```bash
cd backend && LOOPER_PORT=8010 .venv/bin/python main.py   # open http://localhost:8010/demo
```

Tap **Food**, then press Tab until a result name is outlined and press Enter:
the map flies there. Larger findings: #142 (panel hides pins on phones),
#143 (place words match business names).

# #93 — Fixed overlays must not share a corner with map controls (2026-10-03)

`/demo` put the help hint at `left:16px; bottom:16px` and the MapLibre
NavigationControl at `"bottom-left"`. Both took the same corner, so the hint
sat on top of zoom, compass and pitch. On a 390px phone it also covered the
Jarvis dock and the attribution. A screenshot does not show this reliably.
Check it with `document.elementFromPoint` at the centre of each control: on
main all three buttons returned the hint, not the button.

Fix: lift the hint above the control stack (`bottom:112px` ≈ 3×29px buttons +
10px margin + gap). On ≤480px it starts collapsed behind a 44px `? Tips`
toggle (`aria-expanded`, focus ring, Escape closes). The "needs the API on
localhost:8000" line uses the same rule as `apiBase`: it shows only when there
is no `?api=` and the page is not served under `/web/` (which is where `/demo`
redirects).

Run/verify (beginner):

```bash
cd backend && LOOPER_PORT=8010 .venv/bin/python main.py   # then open http://localhost:8010/demo
```

Desktop: the tips box sits above the + / − / compass buttons, and you can click
all of them. Narrow the window below 480px: the box folds into `? Tips`. Tab to
it and press Enter to open it, then Escape to close it. Repeatable check:
`docs/learnings/93-demo-hint/measure.cjs`.

Still open: on 390px the dock's "Hey Looper" pill wraps beside the control
stack. That is `looper-jarvis.js` (PR #85), so it stays out of scope here; the
controls are still clickable.

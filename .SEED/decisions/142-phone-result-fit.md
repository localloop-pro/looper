# #142 — Phones fit result pins into the map strip above the panel (2026-11-19)

On a phone the open Jarvis result panel spans the map's width and covers its
lower half. So when the panel is at least half the map's width, `fitPoints`
fits the pins between the host's top bar and the panel's top edge. It does
this through a new `LooperMapBus.init({ fitOptions })` hook that
`looper-jarvis.js` fills in. The fit is flat (`pitch: 0`) because MapLibre and
Mapbox `fitBounds` ignore pitch. On the 45° `/demo` map, a tilted fit put the
nearest pin back under the panel.

Hosts can pass `LooperJarvis.init({ topInset })`: a number, or a function that
returns the pixel bottom of their own top bar. `/demo` passes its chip bar.
`llx11` can add the same one-liner for its header. Without it, the top padding
stays at 50 px.

Desktop is unchanged: padding 50, current tilt. The search panel now renders
before the pins are fitted, so the fit uses the panel's final size. We chose
this over collapsing the panel or a bottom sheet because it is the smallest
change and keeps the full list visible.
Rollback: revert the #142 commit; no data or config involved.

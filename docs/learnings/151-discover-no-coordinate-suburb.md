# #151 — A filter that only runs on some rows lets the others through (2026-11-20)

`/api/discover` for a known suburb (e.g. Bondi) relied on the radius check
alone and skipped the suburb-name filter. A business with no lat/lng never
reaches the radius check, so a no-coordinate business from Byron Bay showed up
for "Bondi". Both engines (fallback and graph) had the same gap.

When a check needs data a row may lack, decide what happens to that row on
purpose. Here: with a known suburb, a no-coordinate business is kept only when
its accent-folded suburb contains the requested suburb key. Coordinate-only
searches (no suburb) keep the old behaviour.

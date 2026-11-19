# #142 follow-up — Single-target camera moves land above the phone panel (2026-11-19)

Follow-up to #145 (`142-phone-result-fit.md`), from its review. #145 only
covered `fitPoints` with several pins. One mappable pin (`fitPoints` falls
back to `flyTo`), a named-business lookup (`flyTo` the top match at zoom 17)
and tapping a listed option all still centred the target under the open
phone panel.

While the host `fitOptions` hook is active, `LooperMapBus.flyTo` now fits a
~0.1 m box around the target, capped at the zoom asked for, so the target
lands in the same strip above the panel as `fitPoints`. Desktop (hook returns
null) still flies and centres. The named-business panel now renders before
the camera moves, like the search panel.

Known limit, left for the owner: on a 375x667 phone only ~58 px of map is
left between the `/demo` chip bar and the 46vh panel, so 1 of 5 Food pins
stays under it. Fixing that needs a shorter or collapsible phone panel.
Rollback: revert this commit; no data or config involved.

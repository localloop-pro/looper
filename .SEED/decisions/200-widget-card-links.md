# Issue 200: Widget card links

The widget renders each supplied absolute HTTP(S) card URL as a native link without reconstructing it. Other schemes and malformed or missing URLs produce no link. Result fields and the API message remain text nodes, so they cannot inject markup. This is a presentation-only change; search ordering and the bridge contract remain unchanged.

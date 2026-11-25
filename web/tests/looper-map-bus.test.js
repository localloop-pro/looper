// Message validation in web/jarvis/looper-map-bus.js: bad coordinates never reach the map,
// and only http(s) links render in popups.
// Run: node web/tests/looper-map-bus.test.js (also run by jarvis-sync.test.js, so CI covers it)
"use strict";

const bus = require("../jarvis/looper-map-bus.js");

function fakeMap() {
  const calls = [];
  const rec = (name) => (...args) => { calls.push([name, ...args]); };
  return { calls, flyTo: rec("flyTo"), fitBounds: rec("fitBounds"), easeTo: rec("easeTo"), getZoom: () => 12 };
}

async function run(ok) {
  const quiet = console.warn;
  console.warn = () => {};
  try {
    // hasValidCoords: presence, non-blank, finite, in range
    const v = bus.hasValidCoords;
    ok("map bus: valid coords accepted", v({ lng: 151.27, lat: -33.89 }) && v({ lng: "151.27", lat: "-33.89" }));
    ok("map bus: null/undefined/missing rejected",
      !v(null) && !v({ lng: null, lat: 1 }) && !v({ lng: 1 }) && !v({ lng: undefined, lat: 1 }));
    ok("map bus: blank and whitespace strings rejected", !v({ lng: "", lat: 1 }) && !v({ lng: 1, lat: "  " }));
    ok("map bus: NaN / Infinity / non-numeric rejected",
      !v({ lng: NaN, lat: 1 }) && !v({ lng: 1, lat: Infinity }) && !v({ lng: "N/A", lat: 1 }));
    ok("map bus: out-of-range rejected", !v({ lng: 181, lat: 0 }) && !v({ lng: 0, lat: 999 }) && !v({ lng: 0, lat: -90.1 }));
    ok("map bus: range edges accepted", v({ lng: -180, lat: 90 }) && v({ lng: 180, lat: -90 }));

    // uninitialised bus: methods are no-ops, not throws
    bus.flyTo(1, 1);
    ok("map bus: methods before init() do not throw", true);

    // flyTo / fitPoints validate before touching the map
    const map = fakeMap();
    bus.init(map, { markerLib: null });
    bus.flyTo(NaN, 1);
    bus.flyTo(0, 999);
    bus.flyTo(null, null);
    ok("map bus: flyTo ignores invalid coordinates", map.calls.length === 0, JSON.stringify(map.calls));
    bus.flyTo(151.27, -33.89, 15);
    ok("map bus: flyTo passes valid coordinates through",
      map.calls.length === 1 && map.calls[0][0] === "flyTo" && map.calls[0][1].center[0] === 151.27 && map.calls[0][1].zoom === 15);

    map.calls.length = 0;
    bus.fitPoints([{ lng: null, lat: null }, { lng: "", lat: 5 }, { lng: 500, lat: 5 }]);
    ok("map bus: fitPoints with only invalid points does nothing", map.calls.length === 0);
    bus.fitPoints([{ lng: null, lat: null }, { lng: 151.27, lat: -33.89 }]);
    ok("map bus: fitPoints drops invalid points (a null never becomes 0,0)",
      map.calls.length === 1 && map.calls[0][0] === "flyTo" && map.calls[0][1].center[0] === 151.27);

    // popups: showResults skips bad rows, escapes markup, drops unsafe links
    const html = [];
    function Marker() { this.el = null; }
    Marker.prototype.setLngLat = function (c) { this.ll = c; return this; };
    Marker.prototype.setPopup = function (p) { this.popup = p; return this; };
    Marker.prototype.addTo = function () { return this; };
    Marker.prototype.remove = function () {};
    Marker.prototype.getLngLat = function () { return { lng: this.ll[0], lat: this.ll[1] }; };
    function Popup() {}
    Popup.prototype.setHTML = function (h) { html.push(h); return this; };
    global.document = { createElement: () => ({ setAttribute() {} }) };
    const map2 = fakeMap();
    bus.init(map2, { markerLib: { Marker, Popup }, claimCta: { url: "javascript:alert(1)", label: "Claim" } });
    bus.showResults([
      { name: "No coords", lng: null, lat: null },
      { name: "<img src=x onerror=alert(1)>", lng: 151.27, lat: -33.89, category: "café", avg_rating: "4", review_count: 1,
        card_url: "javascript:alert(1)", website: "data:text/html,hi" },
      { name: "Card cafe", lng: 151.28, lat: -33.9, card_url: "https://hybridcard.ai/c/x" },
    ]);
    ok("map bus: showResults skips rows with invalid coordinates", html.length === 2, String(html.length));
    ok("map bus: popup escapes markup in names", !html[0].includes("<img") && html[0].includes("&lt;img"));
    ok("map bus: popup drops javascript:/data: links", !/javascript:|data:text/.test(html[0]));
    ok("map bus: popup renders an https card link", html[1].includes('href="https://hybridcard.ai/c/x"'));
  } finally {
    console.warn = quiet;
    delete global.document;
  }
}

module.exports = { run };

if (require.main === module) {
  let failed = 0;
  run((name, cond, detail) => {
    if (cond) console.log(`ok   - ${name}`);
    else { failed++; console.error(`FAIL - ${name}${detail ? `\n  ${detail}` : ""}`); }
  }).then(() => process.exit(failed ? 1 : 0), (e) => { console.error(e); process.exit(1); });
}

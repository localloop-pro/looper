/* Tests for tools/jarvis-sync-check.js (looper#39).
 * Run: node web/tests/jarvis-sync.test.js
 * Node-only, zero deps — same style as voice-command-router.test.js.
 */
"use strict";

const sync = require("../../tools/jarvis-sync-check.js");
const looper = require("../jarvis/voice-command-router.js");

let passed = 0;
let failed = 0;

function ok(name, cond, detail) {
  if (cond) {
    passed++;
    console.log(`ok   - ${name}`);
  } else {
    failed++;
    console.error(`FAIL - ${name}${detail ? `\n  ${detail}` : ""}`);
  }
}

// ---- Looper's own copy is the contract ------------------------------------
const own = sync.run({});
ok("web/jarvis SUBURBS == /api/discover SUBURB_COORDS, wake regexes exported",
  own.length === 0, own.join("\n  "));

// ---- discover.py parser ----------------------------------------------------
const parsed = sync.parseSuburbCoords(
  'X = 1\nSUBURB_COORDS = {\n    "redfern": (-33.8930, 151.2040),\n    "byron bay": (-28.6474, 153.6120),\n}\n');
ok("parser reads name, lat, lng",
  JSON.stringify(parsed) === JSON.stringify({ redfern: { lat: -33.893, lng: 151.204 }, "byron bay": { lat: -28.6474, lng: 153.612 } }),
  JSON.stringify(parsed));

// ---- suburb drift is caught (the map copy at localloop.pro-main@761d3a1) ---
const coords = { redfern: { lat: -33.893, lng: 151.204 }, bondi: { lat: -33.8915, lng: 151.2743 } };
const stale = { SUBURBS: { bondi: { lat: -33.8915, lng: 151.2743, zoom: 14.5 }, manly: { lat: -33.79, lng: 151.28 } } };
const subProblems = sync.checkSuburbs("map", stale, coords);
ok("missing suburb reported", subProblems.some((p) => p.includes('missing "redfern"')), subProblems.join(" | "));
ok("extra suburb reported", subProblems.some((p) => p.includes('"manly"')), subProblems.join(" | "));
const moved = { SUBURBS: { redfern: { lat: -33.0, lng: 151.204 }, bondi: { lat: -33.8915, lng: 151.2743 } } };
ok("moved suburb reported", sync.checkSuburbs("map", moved, coords).some((p) => p.includes("is at")));

// ---- wake vocabulary drift is caught ---------------------------------------
ok("missing WAKE_RE / WAKE_STRICT_RE reported", sync.checkWakeExports("map", { route() {} }).length === 2);
ok("Looper exports both wake regexes", sync.checkWakeExports("looper", looper).length === 0);

// A router that only knows "hey/ok/okay looper" — the map's STOP_RE today.
const oldStop = /^(?:(?:hey|ok|okay)\s+looper[,!]?\s*)?(?:please\s+)?stop$/;
const oldRouter = {
  route(t) {
    const c = looper.route(t);
    if (c.intent === "stop" && !oldStop.test(looper.clean(t))) return { intent: "search", searchTerm: looper.clean(t) };
    return c;
  },
};
const probeProblems = sync.checkProbes("map", oldRouter, looper);
ok('"okay loopa stop" drift reported', probeProblems.some((p) => p.includes('"okay loopa stop"')), probeProblems.join(" | "));
ok("identical router reports nothing", sync.checkProbes("looper", looper, looper).length === 0);

// ---- the probes really exercise the gaps named in #39 ----------------------
ok('Looper: "okay loopa stop" is a stop', looper.route("okay loopa stop").intent === "stop");
ok('Looper: "cafes in redfern" scopes to redfern', looper.route("cafes in redfern").suburb === "redfern");
ok("probes include every #39 gap",
  ["okay loopa stop", "cafes in redfern", "fly to surry hills", "go to alexandria"].every((p) => sync.PROBES.includes(p)));

// ---- dock must read the router's wake regexes ------------------------------
ok("local WAKE_RE in looper-jarvis.js reported",
  sync.checkJarvisDock("map", "var WAKE_RE = /^(?:hey|ok|okay)\\s+looper\\b/;").length === 1);
ok("Router.WAKE_RE in looper-jarvis.js accepted",
  sync.checkJarvisDock("map", "var WAKE_RE = Router.WAKE_RE || x; var WAKE_STRICT_RE = Router.WAKE_STRICT_RE || x;").length === 0);
const ownDock = require("fs").readFileSync(require("path").join(__dirname, "../jarvis/looper-jarvis.js"), "utf8");
ok("Looper's own looper-jarvis.js reads Router.WAKE_*", sync.checkJarvisDock("looper", ownDock).length === 0);

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);

#!/usr/bin/env node
/* Jarvis sync check (looper#39).
 *
 * The live map (localloop.pro-main) ships its own copy of the Jarvis voice
 * router at assets/js/jarvis/voice-command-router.js. Router changes land
 * here first, in web/jarvis/. This script says whether a router copy has
 * drifted from Looper's contract:
 *
 *   1. its SUBURBS keys and lat/lng equal /api/discover's SUBURB_COORDS
 *      (backend/routes/discover.py), so "cafés in Redfern" flies the map to
 *      the suburb the API will search;
 *   2. it exports WAKE_RE / WAKE_STRICT_RE (the hands-free gate reads them);
 *   3. a fixed list of spoken phrases (wake mishears, barge-in, suburbs)
 *      routes the same way as Looper's web/jarvis router.
 *
 * Usage (zero deps, read-only):
 *   node tools/jarvis-sync-check.js                    # Looper's own copy only
 *   node tools/jarvis-sync-check.js --map ../localloop.pro-main
 *
 * Exit 0 = in sync, 1 = drift found, 2 = bad usage / file missing.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const REPO = path.resolve(__dirname, "..");
const LOOPER_ROUTER = path.join(REPO, "web/jarvis/voice-command-router.js");
const DISCOVER_PY = path.join(REPO, "backend/routes/discover.py");
const MAP_ROUTER_REL = "assets/js/jarvis/voice-command-router.js";
const MAP_JARVIS_REL = "assets/js/jarvis/looper-jarvis.js";

// Spoken phrases whose routing must match Looper's router exactly.
const PROBES = [
  "okay loopa stop",
  "hey luper stop",
  "ok looper stop",
  "stop",
  "bus stop near me",
  "hey luper find a cafe",
  "loopa",
  "hey looper",
  "loopa help",
  "cafes in redfern",
  "fly to surry hills",
  "go to alexandria",
  "coffee in bondi",
  "hairdresser in bondi",
];

// Parse SUBURB_COORDS = { "name": (lat, lng), ... } out of discover.py.
function parseSuburbCoords(pySource) {
  const block = /SUBURB_COORDS\s*=\s*\{([\s\S]*?)\n\}/.exec(pySource);
  if (!block) throw new Error("SUBURB_COORDS not found in discover.py");
  const out = {};
  const row = /"([^"]+)"\s*:\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)/g;
  let m;
  while ((m = row.exec(block[1])) !== null) {
    out[m[1]] = { lat: Number(m[2]), lng: Number(m[3]) };
  }
  if (Object.keys(out).length === 0) throw new Error("SUBURB_COORDS is empty");
  return out;
}

function loadRouter(file) {
  const abs = path.resolve(file);
  delete require.cache[abs];
  return require(abs);
}

// Problems (strings) for one router compared with the API suburb table.
function checkSuburbs(label, router, coords) {
  const problems = [];
  const table = router.SUBURBS || {};
  for (const key of Object.keys(coords)) {
    if (!table[key]) {
      problems.push(`${label}: SUBURBS is missing "${key}" (known to /api/discover)`);
      continue;
    }
    const a = table[key];
    const b = coords[key];
    if (Math.abs(a.lat - b.lat) > 1e-4 || Math.abs(a.lng - b.lng) > 1e-4) {
      problems.push(`${label}: "${key}" is at ${a.lat},${a.lng} but /api/discover uses ${b.lat},${b.lng}`);
    }
  }
  for (const key of Object.keys(table)) {
    if (!coords[key]) problems.push(`${label}: SUBURBS has "${key}", which /api/discover does not know`);
  }
  return problems;
}

function checkWakeExports(label, router) {
  const problems = [];
  for (const name of ["WAKE_RE", "WAKE_STRICT_RE"]) {
    if (!(router[name] instanceof RegExp)) {
      problems.push(`${label}: does not export ${name} (hands-free falls back to "hey looper" only)`);
    }
  }
  return problems;
}

// Only the fields that steer the map or the brain.
function routeShape(router, text) {
  const c = router.route(text) || {};
  return JSON.stringify({
    intent: c.intent,
    suburb: c.suburb,
    category: c.category,
    searchTerm: c.searchTerm,
    businessName: c.businessName,
  });
}

function checkProbes(label, router, reference) {
  const problems = [];
  for (const text of PROBES) {
    const want = routeShape(reference, text);
    const got = routeShape(router, text);
    if (want !== got) problems.push(`${label}: "${text}" routes to ${got}, Looper routes it to ${want}`);
  }
  return problems;
}

// The map's dock must read the router's wake regexes, not a local copy.
function checkJarvisDock(label, jarvisSource) {
  if (/Router\.WAKE_STRICT_RE/.test(jarvisSource) && /Router\.WAKE_RE/.test(jarvisSource)) return [];
  return [`${label}: looper-jarvis.js keeps its own WAKE_RE instead of reading Router.WAKE_RE / Router.WAKE_STRICT_RE`];
}

function run(opts) {
  const coords = parseSuburbCoords(fs.readFileSync(opts.discoverPy || DISCOVER_PY, "utf8"));
  const looper = loadRouter(opts.looperRouter || LOOPER_ROUTER);
  let problems = []
    .concat(checkSuburbs("looper web/jarvis", looper, coords))
    .concat(checkWakeExports("looper web/jarvis", looper));
  if (opts.mapRouter) {
    const map = loadRouter(opts.mapRouter);
    problems = problems
      .concat(checkSuburbs("map router", map, coords))
      .concat(checkWakeExports("map router", map))
      .concat(checkProbes("map router", map, looper));
  }
  if (opts.mapJarvis) {
    problems = problems.concat(checkJarvisDock("map", fs.readFileSync(opts.mapJarvis, "utf8")));
  }
  return problems;
}

function main(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--map") {
      const dir = argv[++i];
      if (!dir) { console.error("--map needs the path to a localloop.pro-main checkout"); return 2; }
      opts.mapRouter = path.join(dir, MAP_ROUTER_REL);
      opts.mapJarvis = path.join(dir, MAP_JARVIS_REL);
      for (const f of [opts.mapRouter, opts.mapJarvis]) {
        if (!fs.existsSync(f)) { console.error(`not found: ${f}`); return 2; }
      }
    } else {
      console.error(`unknown argument: ${argv[i]}`);
      return 2;
    }
  }
  const problems = run(opts);
  if (problems.length === 0) {
    console.log(`jarvis-sync: OK${opts.mapRouter ? " (map copy matches Looper)" : " (Looper only; pass --map <dir> to check the map copy)"}`);
    return 0;
  }
  console.error(`jarvis-sync: ${problems.length} problem(s)`);
  for (const p of problems) console.error(`  - ${p}`);
  return 1;
}

module.exports = { PROBES, parseSuburbCoords, checkSuburbs, checkWakeExports, checkProbes, checkJarvisDock, run };

if (require.main === module) process.exit(main(process.argv.slice(2)));

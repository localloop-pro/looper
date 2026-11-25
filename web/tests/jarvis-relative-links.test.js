/* Repro for looper#204: relative / protocol-relative card_url and website
 * must NOT render as links (they would resolve against the embedding page).
 * Covers the map popup (looper-map-bus.js) and the options panel
 * (looper-jarvis.js). Run: node web/tests/jarvis-relative-links.test.js
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");


const BAD = ["/card/abc", "//evil.example/x", "card/abc", "./card", "?a=1", "#frag"];
const GOOD = "https://hybridcard.ai/c/Abc?x=1";

function popupFor(r) {
  const html = [];
  const sandbox = {
    console, URL, location: { href: "https://localloop.ai/" },
    document: { createElement: () => ({ setAttribute() {}, className: "", title: "" }) },
  };
  sandbox.self = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../jarvis/looper-map-bus.js"), "utf8"), sandbox);
  const Popup = function () { this.setHTML = (h) => { html.push(h); return this; }; };
  const Marker = function () {
    this.setLngLat = () => this; this.setPopup = () => this; this.addTo = () => this;
    this.remove = () => {}; this.getLngLat = () => ({ lng: 0, lat: 0 });
  };
  const map = { fitBounds() {}, easeTo() {}, flyTo() {}, getZoom: () => 1 };
  sandbox.LooperMapBus.init(map, { markerLib: { Marker, Popup } });
  sandbox.LooperMapBus.showResults([Object.assign({ name: "X", lng: 151, lat: -33 }, r)]);
  return html[0] || "";
}

function run(ok) {
  for (const bad of BAD) {
    const a = popupFor({ card_url: bad });
    ok(`popup: card_url ${JSON.stringify(bad)} not rendered as a link`, !/View card/.test(a), a);
    const b = popupFor({ website: bad });
    ok(`popup: website ${JSON.stringify(bad)} not rendered as a link`, !/Website/.test(b), b);
    ok(`popup: claim CTA kept for ${JSON.stringify(bad)} website`, /looper-popup-claim/.test(b), b);
  }
  ok("popup: absolute card_url kept verbatim", popupFor({ card_url: GOOD }).includes(`href="${GOOD}"`));

}

module.exports = { run };

if (require.main === module) {
  let passed = 0, failed = 0;
  run((name, cond, detail) => {
    if (cond) { passed++; console.log(`ok   - ${name}`); }
    else { failed++; console.error(`FAIL - ${name}${detail ? `\n  ${detail}` : ""}`); }
  });
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
}

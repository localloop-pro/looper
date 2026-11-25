/* Node tests for what the Jarvis dock SAYS about failures and distance
 * (looper#153): a 4xx is a bad request, not "brain offline"; network
 * errors and 5xx stay "brain offline"; "within N kilometres" only when a
 * result has a known distance.
 *
 * Runs the real web/jarvis/looper-jarvis.js in a node:vm sandbox with a
 * tiny fake DOM, stubbed map bus/face/speech and a stubbed fetch — no
 * browser needed. Zero deps.
 * Run: node web/tests/jarvis-honesty.test.js
 * (jarvis-sync.test.js also runs it, so CI's existing command covers it.)
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const Router = require("../jarvis/voice-command-router.js");

const SRC = fs.readFileSync(path.join(__dirname, "../jarvis/looper-jarvis.js"), "utf8");

function fakeEl() {
  const kids = {};
  const classes = new Set();
  return {
    style: { setProperty() {} },
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      toggle: (c) => (classes.has(c) ? classes.delete(c) : classes.add(c)),
      contains: (c) => classes.has(c),
    },
    innerHTML: "",
    textContent: "",
    value: "",
    addEventListener() {},
    appendChild() {},
    focus() {},
    querySelector: (sel) => (kids[sel] = kids[sel] || fakeEl()),
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }),
  };
}

// A fresh dock whose /search answers with `answer(url)`:
// { status, body } for an HTTP reply, or { networkError: true }.
function boot(answer) {
  const spoken = [];
  const body = fakeEl();
  body.appendChild = (el) => { body.__wrap = el; }; // the dock's #looper-jarvis
  const sandbox = {
    console,
    performance,
    URL,
    URLSearchParams,
    AbortController,
    setTimeout,
    clearTimeout,
    innerWidth: 900,
    innerHeight: 700,
    location: { href: "https://localloop.ai/", search: "" },
    document: {
      hidden: false,
      head: fakeEl(),
      body,
      getElementById: () => null,
      createElement: () => fakeEl(),
      addEventListener() {},
    },
    // a recognizer exists, so the typed input starts CLOSED (like Chrome)
    webkitSpeechRecognition: function () { return { start() {}, stop() {}, abort() {} }; },
    SpeechSynthesisUtterance: function (text) { this.text = text; },
    speechSynthesis: {
      speak: (u) => { spoken.push(u.text); if (u.onend) u.onend(); },
      cancel() {},
      getVoices: () => [],
      addEventListener() {},
    },
    LooperVoiceRouter: Router,
    LooperMapBus: {
      setCategory() {}, clearResults() {}, showResults() {}, flyTo() {},
      hasValidCoords: () => false,
    },
    LooperFace: {
      mount: () => ({ setMood() {}, startTalking() {}, stopTalking() {} }),
    },
    fetch: (url) => {
      const a = answer(String(url));
      if (a.networkError) return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve({
        ok: a.status >= 200 && a.status < 300,
        status: a.status,
        headers: { get: () => null },
        json: () => Promise.resolve(a.body),
      });
    },
  };
  sandbox.self = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(SRC, sandbox, { filename: "looper-jarvis.js" });
  const J = sandbox.LooperJarvis;
  J.init({ apiBase: "http://stub" });
  const ui = (id) => body.__wrap.querySelector(id);
  return {
    async ask(text) {
      spoken.length = 0;
      J.ask(text);
      for (let i = 0; i < 50 && !spoken.length; i++) await new Promise((r) => setTimeout(r, 2));
      return {
        spoken: spoken.join(" "),
        status: ui("#lj-status").textContent,
        html: ui("#lj-panel").innerHTML,
        panel: ui("#lj-panel").innerHTML.replace(/<[^>]*>/g, "").replace(/&#39;/g, "'"),
        inputOpen: ui("#lj-input-row").classList.contains("lj-open"),
      };
    },
  };
}

const VET = { category: "vet", review_count: 0, avg_rating: null, top_review: null, website: null, card_url: null };
const vets = (rows, extra) => Object.assign({
  query: "vet", message: "Here are the options for 'vet'.", total_results: rows.length,
  results: rows.map((r, i) => Object.assign({ business_id: 100 + i, name: "Vet " + (i + 1), lat: null, lng: null }, VET, r)),
}, extra);

async function run(ok) {
  // ---- failures: 4xx is a bad request, everything else is an outage ------
  for (const [label, text, status] of [
    ["search 422", "find me a cafe", 422],
    ["search 400", "find me a cafe", 400],
    ["business 404", "take me to gertrude and alice", 404],
  ]) {
    const dock = boot(() => ({ status, body: { detail: "bad request" } }));
    const r = await dock.ask(text);
    const all = r.status + " " + r.panel + " " + r.spoken;
    ok(`${label}: not reported as brain offline`, !/offline/i.test(all), JSON.stringify(r));
    ok(`${label}: panel says it couldn't read the request`, /couldn't read that request/.test(r.panel), r.panel);
    ok(`${label}: speech says it couldn't read the request`, /couldn't read that request/.test(r.spoken), r.spoken);
    ok(`${label}: typed input left open`, r.inputOpen, JSON.stringify(r));
  }
  for (const [label, text, reply] of [
    ["search 500", "find me a cafe", { status: 500, body: {} }],
    ["search 503", "find me a cafe", { status: 503, body: {} }],
    ["business 502", "take me to gertrude and alice", { status: 502, body: {} }],
    ["search network error", "find me a cafe", { networkError: true }],
  ]) {
    const dock = boot(() => reply);
    const r = await dock.ask(text);
    ok(`${label}: status is brain offline`, r.status === "Looper brain offline", JSON.stringify(r));
    ok(`${label}: apiDown line shown and spoken`,
      /Looper brain is offline/.test(r.panel) && /Looper brain is offline/.test(r.spoken), JSON.stringify(r));
    // the dock starts with the typed input closed; only a 4xx opens it
    ok(`${label}: typed input not forced open`, !r.inputOpen, JSON.stringify(r));
  }

  // ---- radius wording only with a known distance --------------------------
  const cases = [
    ["no known distance", vets([{ distance_km: null }, { distance_km: null }]), /^I found 2 options\. /, /within \d/],
    ["no known distance, API widened", vets([{ distance_km: null }, {}], { widened_to_km: 10 }), /^I found 2 options\. /, /within \d/],
    ["one known distance", vets([{ distance_km: 0.4 }, { distance_km: null }]), /^I found 2 options within 1\.5 kilometres\. /, null],
    ["all known, in range", vets([{ distance_km: 0.4 }, { distance_km: 0.9 }]), /^I found 2 options within 1\.5 kilometres\. /, null],
    ["all known, widened", vets([{ distance_km: 2.3 }, { distance_km: 2.3 }], { widened_to_km: 10 }),
      /^Nothing within 1\.5 kilometres, so I looked further\. The nearest is 2\.3 kilometres away\. I found 2 options within 10 kilometres\. /, null],
  ];
  for (const [label, reply, want, never] of cases) {
    const dock = boot(() => ({ status: 200, body: reply }));
    const r = await dock.ask("find me a vet");
    ok(`speech, ${label}: ${want}`, want.test(r.spoken), r.spoken);
    if (never) ok(`speech, ${label}: no radius claim`, !never.test(r.spoken), r.spoken);
  }

  // ---- business links: absolute http(s) only, verbatim (looper#204) -----
  const BADLINKS = ["/card/abc", "//evil.example/x", "card/abc", "?a=1", "http:///evil.example/x",
    "https://\\evil.example/x", "https://evil.\nexample/x", "javascript:alert(1)", "data:text/html,x", "ftp://evil.example/x"];
  const GOOD = "http://localhost:3000/c/Abc?x=1#f";
  const SITE = "https://example.com/shop?a=1";
  for (const bad of BADLINKS) {
    for (const field of ["card_url", "website"]) {
      const dock = boot(() => ({ status: 200, body: vets([{ [field]: bad }, {}]) }));
      const r = await dock.ask("find me a vet");
      ok(`panel: ${field} ${JSON.stringify(bad)} not rendered`, !/View card|Website/.test(r.html), r.html);
    }
  }
  const dock = boot(() => ({ status: 200, body: vets([{ card_url: GOOD }, { website: SITE }, { card_url: "/x", website: SITE }]) }));
  const good = await dock.ask("find me a vet");
  ok("panel: localhost card_url kept verbatim", good.html.includes(`href="${GOOD}"`), good.html);
  ok("panel: valid website kept verbatim, also as fallback for an invalid card_url",
    good.html.split(`href="${SITE}"`).length === 3, good.html);
}

module.exports = { run };

if (require.main === module) {
  let passed = 0;
  let failed = 0;
  const ok = (name, cond, detail) => {
    if (cond) { passed++; console.log(`ok   - ${name}`); }
    else { failed++; console.error(`FAIL - ${name}${detail ? `\n  ${detail}` : ""}`); }
  };
  run(ok).then(() => {
    console.log(`\n${passed} passed, ${failed} failed`);
    process.exit(failed === 0 ? 0 : 1);
  }, (e) => { console.error(e); process.exit(1); });
}

/* Regression tests for the Kaspa organization identity badge.
 * Run: node web/tests/kaspa-identity.test.js
 * Node-only, zero deps — same style as voice-command-router.test.js.
 *
 * Covers the two review findings on feat/kaspa-org-identity:
 *   1. verified wording expires at expiresAt even when the refresh request stalls,
 *      the stalled request is bounded by a timeout, and retries keep going;
 *   2. remounting the same host invalidates the earlier in-flight refresh so a
 *      late completion cannot render the old badge or arm a second polling loop.
 */
"use strict";

// ---- minimal fake DOM + controllable clock/timers (installed before load) ----
let now = 1_700_000_000_000;
const timers = new Map();
let timerSeq = 0;
global.Date.now = () => now;
Math.random = () => 0; // no refresh jitter: deterministic timeline
global.setTimeout = (fn, ms) => { const id = ++timerSeq; timers.set(id, { at: now + Math.max(0, ms | 0), fn }); return id; };
global.clearTimeout = (id) => { timers.delete(id); };
async function advance(ms) {
  const target = now + ms;
  for (;;) {
    const due = [...timers.entries()].filter(([, t]) => t.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
    if (!due) break;
    now = due[1].at; timers.delete(due[0]); due[1].fn();
    await Promise.resolve(); await Promise.resolve();
  }
  now = target;
  await Promise.resolve(); await Promise.resolve();
}

function el(tag) {
  // Like a real element, assigning innerHTML replaces the children.
  const node = { tagName: tag, children: [], dataset: {}, textContent: "", className: "", _html: "",
    appendChild(c) { this.children.push(c); return c; }, isConnected: true };
  Object.defineProperty(node, "innerHTML", {
    get() { return this._html; },
    set(v) { this._html = v; this.children = []; },
  });
  return node;
}
global.document = { createElement: el, querySelector: () => null };
global.AbortController = class { constructor() { this.signal = { aborted: false, onabort: null }; }
  abort() { this.signal.aborted = true; if (this.signal.onabort) this.signal.onabort(); } };

// fetch stub: each call returns a controllable deferred; records abort signals.
const calls = [];
global.fetch = (url, init) => new Promise((resolve, reject) => {
  const call = { url, init, resolve, reject, aborted: false };
  if (init && init.signal) init.signal.onabort = () => { call.aborted = true; reject(new Error("aborted")); };
  calls.push(call);
});
global.window = { location: { origin: "http://api.test" } };
require("../kaspa-identity.js");
const badge = global.window.LocalLoopKaspaIdentity;

function fresh(domain, ttlMs) {
  return { domain, verificationState: "fresh", verifiedAt: new Date(now).toISOString(),
    expiresAt: new Date(now + ttlMs).toISOString(), ownerAddress: "kaspa:qrs4ss39xxxxxxxxxxxxxxxx", assetId: "abcdef1234567890i0" };
}
function ok(body) { return { ok: true, json: async () => body }; }

let passed = 0, failed = 0;
function check(name, cond, detail) {
  if (cond) { passed++; console.log(`ok   - ${name}`); }
  else { failed++; console.log(`FAIL - ${name}${detail ? `\n  ${detail}` : ""}`); }
}

(async () => {
  // ---- 1. stalled refresh: wording expires on its own clock; request is bounded; retry continues ----
  const host = el("div");
  const p1 = badge.mount(host, { domain: "localloop.kas", apiBase: "http://api.test" });
  await Promise.resolve();
  check("initial render shows loading/unavailable scoped to the domain", host.dataset.state === "unavailable");
  calls[0].resolve(ok(fresh("localloop.kas", 60_000)));
  await p1;
  check("first response renders fresh", host.dataset.state === "fresh");

  await advance(60_000 + 1_000); // expiresAt passed: expiry timer fired, refresh #2 started and is stalling
  check("second refresh was started", calls.length === 2, `calls=${calls.length}`);
  check("badge downgrades to stale at expiresAt while the request stalls",
    host.dataset.state === "stale", `state=${host.dataset.state}`);

  await advance(10_000); // > REQUEST_TIMEOUT_MS: the stalled request is aborted (fail-closed: unavailable)
  check("stalled request is aborted by the timeout", calls[1].aborted === true);
  check("after the timeout the badge is the bounded fail-closed state", host.dataset.state === "unavailable", `state=${host.dataset.state}`);
  await advance(5 * 60 * 1000 + 1000); // fallback interval: retry after failure
  check("retries continue after a timed-out request", calls.length >= 3, `calls=${calls.length}`);
  check("still not fresh without a new successful response", host.dataset.state !== "fresh", `state=${host.dataset.state}`);

  // ---- 2. remount invalidates the in-flight refresh of the previous mount ----
  const host2 = el("div");
  const before = calls.length;
  badge.mount(host2, { domain: "localloop.kas", apiBase: "http://api.test" }); // mount A, request pending
  await Promise.resolve();
  const reqA = calls[before];
  const pB = badge.mount(host2, { domain: "qikflo.kas", apiBase: "http://api.test" }); // mount B replaces A
  await Promise.resolve();
  const reqB = calls[before + 1];
  check("remount aborts the previous in-flight request", reqA.aborted === true);
  reqB.resolve(ok(fresh("qikflo.kas", 60_000)));
  await pB;
  check("new mount renders its own domain", host2.dataset.state === "fresh" &&
    JSON.stringify(host2.children[0].children[0].innerHTML).includes("qikflo.kas"));
  // Late completion of A (even if it had not been aborted) must not render or reschedule.
  const timersBefore = timers.size;
  try { reqA.resolve(ok(fresh("localloop.kas", 60_000))); } catch (_) { /* already rejected */ }
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  check("late completion of the superseded mount does not render the old domain",
    JSON.stringify(host2.children[0].children[0].innerHTML).includes("qikflo.kas"));
  check("late completion does not arm a second polling loop", timers.size === timersBefore, `timers ${timersBefore} -> ${timers.size}`);

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})().catch((err) => { console.error(err); process.exit(1); });

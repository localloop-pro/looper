/* Unit tests for the looper-api-proxy Worker (looper#17: X-Request-ID from cf-ray;
 * looper#28: origin key + detail-free 502).
 * Run: node workers/looper-api-proxy/test/index.test.mjs
 * Node-only, zero deps. global fetch is stubbed; nothing leaves the machine.
 */
import worker, { isSafeRequestId, ORIGIN_KEY_HEADER } from "../src/index.js";

let passed = 0;
let failed = 0;

function check(name, ok, detail) {
  if (ok) {
    passed++;
    console.log(`ok   - ${name}`);
  } else {
    failed++;
    console.error(`FAIL - ${name}${detail ? `\n  ${detail}` : ""}`);
  }
}

const ENV = { ORIGIN: "http://origin.invalid" };
const RAY = "8a1b2c3d4e5f6789-SYD";

// Run the Worker once and return the headers it forwarded to the origin.
async function forwarded(reqHeaders, method = "GET", env = ENV) {
  let seen = null;
  globalThis.fetch = async (url, init) => {
    seen = { url, headers: init.headers };
    return new Response("{}", { status: 200 });
  };
  const req = new Request("https://api.localloop.ai/api/search?q=pizza", {
    method,
    headers: reqHeaders,
    body: method === "POST" ? "{}" : undefined,
  });
  await worker.fetch(req, env);
  return seen;
}

const realFetch = globalThis.fetch;
try {
  // 1. Missing id → cf-ray
  let s = await forwarded({ "cf-ray": RAY });
  check("missing X-Request-ID is set from cf-ray", s.headers.get("x-request-id") === RAY, s.headers.get("x-request-id"));

  // 2. Safe inbound id is kept, even when cf-ray exists
  s = await forwarded({ "x-request-id": "turn-abc12345", "cf-ray": RAY });
  check("safe inbound X-Request-ID is kept", s.headers.get("x-request-id") === "turn-abc12345");

  // 3. Unsafe inbound ids (PII-shaped or malformed) are replaced with cf-ray
  for (const bad of ["0412999888", "a@b.example.com", "Bearer abc.def", "short", "x".repeat(129), "<script>xx"]) {
    s = await forwarded({ "x-request-id": bad, "cf-ray": RAY });
    check(`unsafe inbound id ${JSON.stringify(bad.slice(0, 20))} replaced with cf-ray`, s.headers.get("x-request-id") === RAY);
  }

  // 4. No id and no cf-ray (local wrangler dev) → a fresh uuid, still safe
  s = await forwarded({});
  const id = s.headers.get("x-request-id");
  check("no cf-ray falls back to a safe random id", isSafeRequestId(id), id);

  // 5. POST bodies and other headers still pass through untouched
  s = await forwarded({ "cf-ray": RAY, "x-hc-signature": "sig" }, "POST");
  check("POST forwards signature header and request id", s.headers.get("x-hc-signature") === "sig" && s.headers.get("x-request-id") === RAY);
  check("path and query reach the origin", s.url === "http://origin.invalid/api/search?q=pizza", s.url);

  // 6. Worker's own error responses carry the id
  globalThis.fetch = async () => { throw new Error("down"); };
  let res = await worker.fetch(new Request("https://api.localloop.ai/api/search", { headers: { "cf-ray": RAY } }), ENV);
  check("502 origin_unreachable echoes X-Request-ID", res.status === 502 && res.headers.get("x-request-id") === RAY);
  res = await worker.fetch(new Request("https://api.localloop.ai/api/search", { headers: { "cf-ray": RAY } }), {});
  check("500 ORIGIN unset echoes X-Request-ID", res.status === 500 && res.headers.get("x-request-id") === RAY);

  // 8. Origin key (looper#28)
  const KEYED = { ...ENV, ORIGIN_KEY: "test-origin-key" };
  s = await forwarded({ "cf-ray": RAY }, "GET", KEYED);
  check("ORIGIN_KEY set: key is added", s.headers.get(ORIGIN_KEY_HEADER) === KEYED.ORIGIN_KEY);

  s = await forwarded({ "cf-ray": RAY, [ORIGIN_KEY_HEADER]: "spoofed" }, "POST", KEYED);
  check("ORIGIN_KEY set: inbound spoofed key is replaced",
    s.headers.get(ORIGIN_KEY_HEADER) === KEYED.ORIGIN_KEY, s.headers.get(ORIGIN_KEY_HEADER));

  s = await forwarded({ "cf-ray": RAY, "x-hc-signature": "sig" }, "POST", ENV);
  const baseline = [...s.headers.entries()];
  check("ORIGIN_KEY unset: no key header added", !s.headers.has(ORIGIN_KEY_HEADER));
  s = await forwarded({ "cf-ray": RAY, "x-hc-signature": "sig" }, "POST", { ...ENV, ORIGIN_KEY: "" });
  check("ORIGIN_KEY empty: forwarded headers identical to unset",
    JSON.stringify([...s.headers.entries()]) === JSON.stringify(baseline));
  s = await forwarded({ "cf-ray": RAY, [ORIGIN_KEY_HEADER]: "client-value" }, "GET", ENV);
  check("ORIGIN_KEY unset: request passes through unchanged (as before #28)",
    s.headers.get(ORIGIN_KEY_HEADER) === "client-value");

  // 9. 502 body carries no detail; the error is logged with the request id
  const logged = [];
  const realError = console.error;
  console.error = (...a) => logged.push(a.join(" "));
  globalThis.fetch = async () => { throw new Error("connect ECONNREFUSED http://looper-api.secret-origin.invalid"); };
  try {
    res = await worker.fetch(new Request("https://api.localloop.ai/api/search", { headers: { "cf-ray": RAY } }), KEYED);
  } finally {
    console.error = realError;
  }
  const body = await res.text();
  check("502 body is exactly {ok:false,error:origin_unreachable}",
    res.status === 502 && body === JSON.stringify({ ok: false, error: "origin_unreachable" }), body);
  check("502 body leaks no origin, key or error text",
    !/secret-origin|origin\.invalid|ECONNREFUSED|test-origin-key|detail/.test(body), body);
  check("502 error is logged with the request id",
    logged.some((l) => l.includes(RAY) && l.includes("ECONNREFUSED")), logged.join("|"));

  // 10. The rule matches the backend's (letters required, 8–128 safe chars)
  check("rule: cf-ray shape is safe", isSafeRequestId(RAY));
  check("rule: all digits rejected", !isSafeRequestId("12345678"));
  check("rule: non-string rejected", !isSafeRequestId(null));
} finally {
  globalThis.fetch = realFetch;
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

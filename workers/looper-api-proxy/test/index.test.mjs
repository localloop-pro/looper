/* Unit tests for the looper-api-proxy Worker (looper#17: X-Request-ID from cf-ray).
 * Run: node workers/looper-api-proxy/test/index.test.mjs
 * Node-only, zero deps. global fetch is stubbed; nothing leaves the machine.
 */
import worker, { isSafeRequestId } from "../src/index.js";

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
async function forwarded(reqHeaders, method = "GET") {
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
  await worker.fetch(req, ENV);
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

  // 7. The rule matches the backend's (letters required, 8–128 safe chars)
  check("rule: cf-ray shape is safe", isSafeRequestId(RAY));
  check("rule: all digits rejected", !isSafeRequestId("12345678"));
  check("rule: non-string rejected", !isSafeRequestId(null));
} finally {
  globalThis.fetch = realFetch;
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);

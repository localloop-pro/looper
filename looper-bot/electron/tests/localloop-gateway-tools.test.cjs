"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  PIN_FIELDS,
  buildPendingPinsUrl,
  createLocalLoopGatewayTools,
  validatedBaseUrl,
} = require("../localloop-gateway-tools.cjs");

const TOKEN = "t".repeat(32);
const BASE = "https://looper.localloop.ai";

test("allowlist exactly matches merged SPEC-055", () => {
  assert.deepEqual(PIN_FIELDS, [
    "id", "place_name", "category", "created_at", "source",
    "moderation_status", "business_layer_status", "deal_id",
    "hybrid_card_id", "slug", "business_name", "title",
    "short_description", "hybridcard_category", "discount_pct",
    "marker_size", "latitude", "longitude", "vip_count", "claim_url",
    "source_updated_at",
  ]);
});

test("Electron main registers both gateway tool specs and execution routes", () => {
  const main = fs.readFileSync(path.join(__dirname, "..", "main.cjs"), "utf8");
  for (const name of ["localloop_pending_pins", "localloop_gateway_health"]) {
    assert.match(main, new RegExp(`name: ["']${name}["']`));
    assert.match(main, new RegExp(`if \\(name === ["']${name}["']\\)`));
  }
});

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

function successBody(overrides = {}) {
  return {
    ok: true,
    filters: { source: "hybridcard", status: "pending_review" },
    pagination: { page: 1, limit: 20, returned: 1, total: 1, total_pages: 1, has_next: false },
    pins: [{
      id: "pin-1",
      place_name: "Bondi Barber",
      category: "Offers",
      created_at: "2026-08-12T00:00:00Z",
      source: "hybridcard",
      moderation_status: "pending_review",
      business_name: "Bondi Barber",
      title: "Fresh cut offer",
      deal_id: "deal-1",
      claim_url: "https://bondi-barber.hybridcard.ai",
      raw_payload: { must_not_escape: true },
      owner_mobile: "must-not-escape",
    }],
    ...overrides,
  };
}

test("buildPendingPinsUrl uses only fixed filters and bounded pagination", () => {
  const { url } = buildPendingPinsUrl(`${BASE}/`, { page: 3, limit: 50, source: "other", status: "approved" });
  assert.equal(url.toString(), `${BASE}/api/bot/map/pins?source=hybridcard&status=pending_review&page=3&limit=50`);
  assert.throws(() => buildPendingPinsUrl(BASE, { page: 0 }), /page must be an integer/);
  assert.throws(() => buildPendingPinsUrl(BASE, { limit: 51 }), /limit must be an integer/);
});

test("gateway base rejects token-exfiltration URLs before fetch", async () => {
  assert.equal(validatedBaseUrl("https://looper.localloop.ai/"), BASE);
  assert.equal(validatedBaseUrl("http://127.0.0.1:8787"), "http://127.0.0.1:8787");
  assert.throws(() => validatedBaseUrl("http://attacker.invalid"), /must use HTTPS/);
  assert.throws(() => validatedBaseUrl("https://user:pass@looper.localloop.ai"), /without credentials/);
  assert.throws(() => validatedBaseUrl("https://looper.localloop.ai/redirect"), /without credentials/);

  let calls = 0;
  const tools = createLocalLoopGatewayTools({
    baseUrl: "http://attacker.invalid",
    readToken: TOKEN,
    fetchImpl: async () => { calls += 1; },
  });
  const result = await tools.readPendingPins();
  assert.equal(result.error, "invalid_gateway_url");
  assert.equal(calls, 0);
});

test("pending-pin reader fails before fetch when machine auth is absent", async () => {
  let calls = 0;
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: "short",
    fetchImpl: async () => { calls += 1; },
  });
  const result = await tools.readPendingPins();
  assert.equal(result.ok, false);
  assert.equal(result.missingEnv, "LOOPER_BOT_READ_TOKEN");
  assert.equal(calls, 0);
});

test("pending-pin reader sends bearer auth and returns a safe table artifact", async () => {
  let requestUrl;
  let requestOptions;
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async (url, options) => {
      requestUrl = String(url);
      requestOptions = options;
      return jsonResponse(200, successBody());
    },
  });
  const result = await tools.readPendingPins();
  assert.equal(requestUrl, `${BASE}/api/bot/map/pins?source=hybridcard&status=pending_review&page=1&limit=20`);
  assert.equal(requestOptions.method, "GET");
  assert.equal(requestOptions.redirect, "error");
  assert.ok(requestOptions.signal instanceof AbortSignal);
  assert.equal(requestOptions.headers.Authorization, `Bearer ${TOKEN}`);
  assert.equal(result.ok, true);
  assert.equal(result.pending_count, 1);
  assert.match(result.artifact.content, /Bondi Barber/);
  assert.match(result.artifact.content, /audit row/);
  assert.doesNotMatch(result.artifact.content, /must-not-escape/);
  assert.deepEqual(Object.keys(result.pins[0]), PIN_FIELDS);
  assert.equal(result.pins[0].owner_mobile, undefined);
  assert.equal(result.pins[0].raw_payload, undefined);
});

test("unsafe claim links are removed before rendering", async () => {
  const body = successBody();
  body.pins[0].claim_url = "javascript:alert(1)";
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, body),
  });
  const result = await tools.readPendingPins();
  assert.equal(result.pins[0].claim_url, null);
  assert.doesNotMatch(result.artifact.content, /javascript:/);

  body.pins[0].claim_url = "https://phishing.invalid/card";
  const phishing = await tools.readPendingPins();
  assert.equal(phishing.pins[0].claim_url, null);
  assert.doesNotMatch(phishing.artifact.content, /phishing\.invalid/);
});

test("untrusted business text is escaped in the Markdown table", async () => {
  const body = successBody();
  body.pins[0].business_name = "<script>alert(1)</script> | [click](javascript:bad)";
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, body),
  });
  const result = await tools.readPendingPins();
  assert.doesNotMatch(result.artifact.content, /<script>/);
  assert.doesNotMatch(result.artifact.content, / \| \[click\]/);
  assert.match(result.artifact.content, /&lt;script&gt;/);
});

test("empty beyond-total page preserves exact total", async () => {
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, successBody({
      pagination: { page: 9, limit: 20, returned: 0, total: 3, total_pages: 1, has_next: false },
      pins: [],
    })),
  });
  const result = await tools.readPendingPins({ page: 9 });
  assert.equal(result.ok, true);
  assert.equal(result.pending_count, 3);
  assert.deepEqual(result.pins, []);
  assert.match(result.artifact.content, /No pending HybridCard pins/);
});

test("audit failures expose no queue data and do not echo arbitrary bodies", async () => {
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(502, { error: "audit_failed", detail: "secret backend detail" }),
  });
  const result = await tools.readPendingPins();
  assert.deepEqual(result, {
    ok: false,
    status: 502,
    error: "audit_failed",
    message: "The gateway could not audit this read, so it correctly withheld all queue data.",
  });
  assert.equal(result.pins, undefined);
  assert.doesNotMatch(JSON.stringify(result), /secret backend detail/);
});

test("malformed success response fails closed", async () => {
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, { ok: true, pins: [{ raw_payload: "no" }] }),
  });
  const result = await tools.readPendingPins();
  assert.equal(result.ok, false);
  assert.equal(result.error, "invalid_gateway_response");
  assert.equal(result.pins, undefined);
});

test("pagination metadata must agree with the returned pins", async () => {
  const body = successBody();
  body.pagination.returned = 0;
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, body),
  });
  const result = await tools.readPendingPins();
  assert.equal(result.ok, false);
  assert.equal(result.error, "invalid_gateway_response");
});

test("a pin outside the fixed source or moderation status fails closed", async () => {
  const body = successBody();
  body.pins[0].moderation_status = "approved";
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, body),
  });
  const result = await tools.readPendingPins();
  assert.equal(result.ok, false);
  assert.equal(result.error, "invalid_gateway_response");
  assert.equal(result.pins, undefined);
});

test("gateway cannot substitute a different page or limit", async () => {
  const body = successBody({
    pagination: { page: 2, limit: 20, returned: 1, total: 21, total_pages: 2, has_next: false },
  });
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    readToken: TOKEN,
    fetchImpl: async () => jsonResponse(200, body),
  });
  const result = await tools.readPendingPins({ page: 1, limit: 20 });
  assert.equal(result.ok, false);
  assert.equal(result.error, "invalid_gateway_response");
});

test("gateway health is public, read-only, and allowlisted", async () => {
  let request;
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE,
    fetchImpl: async (url, options) => {
      request = { url, options };
      return jsonResponse(200, {
        ok: true,
        service: "looper-gateway",
        version: "0.1.0",
        mode: "connector-first",
        internal_secret: "must-not-escape",
      });
    },
  });
  const result = await tools.health();
  assert.equal(request.url, `${BASE}/health`);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.Authorization, undefined);
  assert.equal(result.ok, true);
  assert.equal(result.internal_secret, undefined);
  assert.doesNotMatch(result.artifact.content, /must-not-escape/);
});

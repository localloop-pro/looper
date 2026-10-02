"use strict";

// Cross-repo contract (looper#31, rows O1/O2 in docs/CROSS-REPO-CONTRACTS.md).
// Feeds the reader the LocalLoop gateway's REAL response shapes, copied from
// localloop-pro/localloop.pro-main @ 761d3a124dd4965c3454dc28e6050ebfbf7f2b36:
//   pending pins: workers/looper-gateway/src/pin-read.mjs#L221-L248 (toPublicPin)
//                 + #L284-L313 (handlePendingPinRead)
//   errors:       workers/looper-gateway/src/index.mjs#L1188-L1238 (errorResponse)
//   health:       workers/looper-gateway/src/index.mjs#L198-L207
//   live mode:    workers/looper-gateway/src/platform-proxy.mjs#L8 (looper#50)
// If the gateway changes one of these, update the copy here and the doc row.

const test = require("node:test");
const assert = require("node:assert/strict");

const { PIN_FIELDS, createLocalLoopGatewayTools } = require("../localloop-gateway-tools.cjs");

const TOKEN = "t".repeat(32);
const BASE = "https://looper.localloop.ai";

function reply(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

// toPublicPin() output key order, field for field.
const GATEWAY_PIN_KEYS = [
  "id", "place_name", "category", "created_at", "source", "moderation_status",
  "business_layer_status", "deal_id", "hybrid_card_id", "slug", "business_name",
  "title", "short_description", "hybridcard_category", "discount_pct", "marker_size",
  "latitude", "longitude", "vip_count", "claim_url", "source_updated_at",
];

function gatewayPin(id) {
  return {
    id, place_name: "Bondi Barber", category: "Offers", created_at: "2026-10-01T00:00:00Z",
    source: "hybridcard", moderation_status: "pending_review",
    business_layer_status: null, deal_id: "deal-1", hybrid_card_id: "card-1",
    slug: "bondi-barber", business_name: "Bondi Barber", title: "Fresh cut offer",
    short_description: null, hybridcard_category: "health", discount_pct: 20,
    marker_size: "medium", latitude: -33.89, longitude: 151.27, vip_count: 0,
    claim_url: "http://localhost:3000/c/bondi-barber", source_updated_at: null,
  };
}

// handlePendingPinRead() with page/limit/total as given.
function gatewayPage(page, limit, total, count) {
  const totalPages = total === 0 ? 0 : Math.ceil(total / limit);
  return {
    ok: true,
    filters: { source: "hybridcard", status: "pending_review" },
    pagination: { page, limit, returned: count, total, total_pages: totalPages, has_next: page < totalPages },
    pins: Array.from({ length: count }, (_, i) => gatewayPin(`pin-${page}-${i}`)),
  };
}

test("reader's pin allowlist equals the gateway's toPublicPin keys", () => {
  assert.deepEqual([...PIN_FIELDS], GATEWAY_PIN_KEYS);
});

test("gateway success shape (incl. empty queue) passes the reader's validation", async () => {
  for (const [page, limit, total, count] of [[1, 20, 2, 2], [1, 20, 0, 0], [2, 1, 3, 1], [5, 20, 3, 0]]) {
    let seen;
    const tools = createLocalLoopGatewayTools({
      baseUrl: BASE, readToken: TOKEN,
      fetchImpl: async (url, options) => { seen = { url: new URL(url), options }; return reply(200, gatewayPage(page, limit, total, count)); },
    });
    const result = await tools.readPendingPins({ page, limit });
    assert.equal(result.ok, true, JSON.stringify(result));
    assert.equal(result.pending_count, total);
    assert.equal(result.pins.length, count);
    // Request: the only four params parseQuery() allows, bearer auth.
    assert.equal(seen.url.pathname, "/api/bot/map/pins");
    assert.deepEqual([...seen.url.searchParams.keys()].sort(), ["limit", "page", "source", "status"]);
    assert.equal(seen.options.headers.Authorization, `Bearer ${TOKEN}`);
  }
});

test("every PinReadError code the gateway can emit maps to a known reader error", async () => {
  const codes = [[401, "unauthorized"], [422, "invalid_query"], [503, "read_auth_not_configured"],
    [503, "read_backend_not_configured"], [502, "select_failed"], [502, "audit_failed"]];
  for (const [status, code] of codes) {
    const tools = createLocalLoopGatewayTools({
      baseUrl: BASE, readToken: TOKEN,
      fetchImpl: async () => reply(status, { ok: false, error: code, message: status < 500 ? "x" : "internal_error" }),
    });
    const result = await tools.readPendingPins();
    assert.equal(result.ok, false);
    assert.equal(result.error, code);
  }
});

test("gateway live mode (looper#50) is named and fails safe with no queue data", async () => {
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE, readToken: TOKEN,
    fetchImpl: async () => reply(503, { error: "migration_endpoint_pending", detail: "must-not-escape" }),
  });
  const result = await tools.readPendingPins();
  assert.equal(result.ok, false);
  assert.equal(result.status, 503);
  assert.equal(result.error, "migration_endpoint_pending");
  assert.match(result.message, /PLATFORM_ENV=live/);
  assert.equal(result.pins, undefined);
  assert.equal(result.artifact, undefined);
  assert.doesNotMatch(JSON.stringify(result), /must-not-escape/);

  const health = await tools.health();
  assert.deepEqual(Object.keys(health).sort(), ["error", "message", "ok", "status"]);
  assert.equal(health.ok, false);
  assert.equal(health.status, 503);
  assert.equal(health.error, "migration_endpoint_pending");
  assert.match(health.message, /PLATFORM_ENV=live/);
  assert.doesNotMatch(JSON.stringify(health), /must-not-escape/);
});

test("gateway /health shape is read as healthy", async () => {
  const tools = createLocalLoopGatewayTools({
    baseUrl: BASE, readToken: TOKEN,
    fetchImpl: async () => reply(200, {
      ok: true, service: "looper-gateway", version: "0.1.0", mode: "connector-first",
      headAgent: "LOOPER", router: "Pi", byok: "disabled-v1",
    }),
  });
  const result = await tools.health();
  assert.equal(result.ok, true);
  assert.equal(result.service, "looper-gateway");
  assert.equal(result.mode, "connector-first");
});

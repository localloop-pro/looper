"use strict";

// Sanctioned read-only LocalLoop Bot Gateway client (SPEC-055).
// This module intentionally has no Supabase dependency: Looper must only read
// the pending queue through the machine-authenticated, audited gateway API.

const PENDING_PINS_PATH = "/api/bot/map/pins";
const FIXED_SOURCE = "hybridcard";
const FIXED_STATUS = "pending_review";
const MIN_TOKEN_BYTES = 32;
const PIN_FIELDS = [
  "id",
  "place_name",
  "category",
  "created_at",
  "source",
  "moderation_status",
  "business_layer_status",
  "deal_id",
  "hybrid_card_id",
  "slug",
  "business_name",
  "title",
  "short_description",
  "hybridcard_category",
  "discount_pct",
  "marker_size",
  "latitude",
  "longitude",
  "vip_count",
  "claim_url",
  "source_updated_at",
];
const KNOWN_GATEWAY_ERRORS = new Set([
  "unauthorized",
  "invalid_query",
  "read_auth_not_configured",
  "read_backend_not_configured",
  "select_failed",
  "audit_failed",
]);

function normalizeBaseUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function validatedBaseUrl(value) {
  const normalized = normalizeBaseUrl(value);
  if (!normalized) throw new Error("LOCALLOOP_GATEWAY_URL is not configured");
  const url = new URL(normalized);
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || !["", "/"].includes(url.pathname)) {
    throw new Error("LOCALLOOP_GATEWAY_URL must be an origin without credentials, path, query, or fragment");
  }
  if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) {
    throw new Error("LOCALLOOP_GATEWAY_URL must use HTTPS (HTTP is allowed only for loopback development)");
  }
  return url.origin;
}

function boundedInteger(value, fallback, min, max, name) {
  if (value === undefined || value === null || value === "") return fallback;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new Error(`${name} must be an integer from ${min} to ${max}`);
  }
  return parsed;
}

function buildPendingPinsUrl(baseUrl, args = {}) {
  const normalized = validatedBaseUrl(baseUrl);
  const page = boundedInteger(args.page, 1, 1, 10000, "page");
  const limit = boundedInteger(args.limit, 20, 1, 50, "limit");
  const url = new URL(PENDING_PINS_PATH, `${normalized}/`);
  url.searchParams.set("source", FIXED_SOURCE);
  url.searchParams.set("status", FIXED_STATUS);
  url.searchParams.set("page", String(page));
  url.searchParams.set("limit", String(limit));
  return { url, page, limit };
}

function sanitizePin(value) {
  const source = value && typeof value === "object" ? value : {};
  const pin = Object.fromEntries(PIN_FIELDS.map((field) => [field, source[field] ?? null]));
  pin.claim_url = safeClaimUrl(pin.claim_url);
  return pin;
}

function safeClaimUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value));
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) return null;
    const hybridCardHost = url.hostname === "hybridcard.ai" || url.hostname.endsWith(".hybridcard.ai");
    if (!hybridCardHost && !loopback) return null;
    return url.href.replace(/\)/g, "%29");
  } catch {
    return null;
  }
}

function markdownCell(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\[/g, "\\[")
    .replace(/\]/g, "\\]")
    .replace(/`/g, "\\`")
    .replace(/\|/g, "\\|")
    .replace(/[\r\n]+/g, " ")
    .trim();
}

function pendingPinsArtifact(data) {
  const pagination = data.pagination;
  const pins = data.pins;
  const summary = [
    `**Pending HybridCard pins:** ${pagination.total}`,
    `**Page:** ${pagination.page}/${Math.max(1, pagination.total_pages)} · **Returned:** ${pagination.returned} · **Has next:** ${pagination.has_next ? "yes" : "no"}`,
  ];
  if (pins.length === 0) {
    summary.push("", "_No pending HybridCard pins on this page._");
  } else {
    const rows = pins.map((pin) => [
      markdownCell(pin.created_at),
      markdownCell(pin.business_name || pin.place_name),
      markdownCell(pin.hybridcard_category || pin.category),
      markdownCell(pin.title),
      markdownCell(pin.deal_id),
      pin.claim_url ? `[View card](${pin.claim_url})` : "",
    ]);
    summary.push(
      "",
      "| Created | Business | Category | Offer | Deal | Card |",
      "|---|---|---|---|---|---|",
      ...rows.map((row) => `| ${row.join(" | ")} |`),
    );
  }
  summary.push("", "_Read-only. The gateway committed an audit row before returning this queue data._");
  return {
    title: "HybridCard pins awaiting approval",
    kind: "markdown",
    content: summary.join("\n"),
  };
}

function validPendingPinsResponse(data) {
  if (!data || data.ok !== true || !data.filters || !data.pagination || !Array.isArray(data.pins)) return false;
  if (data.filters.source !== FIXED_SOURCE || data.filters.status !== FIXED_STATUS) return false;
  const p = data.pagination;
  if (!["page", "limit", "returned", "total", "total_pages"].every((key) => Number.isInteger(p[key]))) return false;
  if (typeof p.has_next !== "boolean") return false;
  if (p.page < 1 || p.page > 10000 || p.limit < 1 || p.limit > 50) return false;
  if (p.returned < 0 || p.returned > p.limit || p.returned !== data.pins.length || p.total < 0 || p.total_pages < 0) return false;
  if (p.total_pages !== Math.ceil(p.total / p.limit)) return false;
  if (!data.pins.every((pin) => pin && typeof pin === "object"
      && typeof pin.id === "string" && pin.id.length > 0
      && pin.source === FIXED_SOURCE && pin.moderation_status === FIXED_STATUS)) return false;
  return true;
}

function gatewayErrorResult(response, body) {
  const candidate = body && typeof body.error === "string" ? body.error : "gateway_read_failed";
  const error = KNOWN_GATEWAY_ERRORS.has(candidate) ? candidate : "gateway_read_failed";
  const messages = {
    unauthorized: "The pending-pin reader is not authorized. Check LOOPER_BOT_READ_TOKEN.",
    invalid_query: "The gateway rejected the pending-pin pagination request.",
    read_auth_not_configured: "The LocalLoop gateway read token is not configured.",
    read_backend_not_configured: "The LocalLoop gateway read backend is not configured.",
    select_failed: "The pending-pin queue is temporarily unavailable.",
    audit_failed: "The gateway could not audit this read, so it correctly withheld all queue data.",
    gateway_read_failed: "The pending-pin gateway request failed safely.",
  };
  return { ok: false, status: response.status, error, message: messages[error] };
}

function createLocalLoopGatewayTools({ baseUrl, readToken, fetchImpl = globalThis.fetch, timeoutMs = 10000 } = {}) {
  let normalizedBaseUrl = "";
  let baseUrlError = null;
  try {
    normalizedBaseUrl = validatedBaseUrl(baseUrl);
  } catch (error) {
    baseUrlError = error;
  }
  const token = String(readToken || "").trim();

  async function readPendingPins(args = {}) {
    if (baseUrlError) {
      return {
        ok: false,
        missingEnv: "LOCALLOOP_GATEWAY_URL",
        error: "invalid_gateway_url",
        message: baseUrlError.message,
      };
    }
    if (Buffer.byteLength(token, "utf8") < MIN_TOKEN_BYTES) {
      return {
        ok: false,
        missingEnv: "LOOPER_BOT_READ_TOKEN",
        error: "read_token_not_configured",
        message: "LOOPER_BOT_READ_TOKEN must be the same 32+ byte secret configured in the LocalLoop Worker.",
      };
    }

    let request;
    try {
      request = buildPendingPinsUrl(normalizedBaseUrl, args);
    } catch (error) {
      return { ok: false, error: "invalid_pagination", message: error.message };
    }

    try {
      const response = await fetchImpl(request.url, {
        method: "GET",
        redirect: "error",
        signal: AbortSignal.timeout(timeoutMs),
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      let body = {};
      try {
        body = await response.json();
      } catch {}
      if (!response.ok) return gatewayErrorResult(response, body);
      if (!validPendingPinsResponse(body)
          || body.pagination.page !== request.page
          || body.pagination.limit !== request.limit) {
        return {
          ok: false,
          status: response.status,
          error: "invalid_gateway_response",
          message: "The gateway returned an unexpected pending-pin response shape; no queue data was shown.",
        };
      }

      const data = {
        filters: { source: FIXED_SOURCE, status: FIXED_STATUS },
        pagination: {
          page: body.pagination.page,
          limit: body.pagination.limit,
          returned: body.pagination.returned,
          total: body.pagination.total,
          total_pages: body.pagination.total_pages,
          has_next: body.pagination.has_next,
        },
        pins: body.pins.map(sanitizePin),
      };
      return {
        ok: true,
        ...data,
        pending_count: data.pagination.total,
        artifact: pendingPinsArtifact(data),
      };
    } catch {
      return {
        ok: false,
        error: "gateway_unreachable",
        message: "The LocalLoop gateway is offline or unreachable; no queue data was returned.",
      };
    }
  }

  async function health() {
    if (baseUrlError) {
      return {
        ok: false,
        missingEnv: "LOCALLOOP_GATEWAY_URL",
        error: "invalid_gateway_url",
        message: baseUrlError.message,
      };
    }
    try {
      const response = await fetchImpl(`${normalizedBaseUrl}/health`, {
        method: "GET",
        redirect: "error",
        signal: AbortSignal.timeout(timeoutMs),
        headers: { Accept: "application/json" },
      });
      let body = {};
      try {
        body = await response.json();
      } catch {}
      if (!response.ok) {
        return { ok: false, status: response.status, error: "gateway_health_failed", message: "LocalLoop gateway health check failed." };
      }
      const status = {
        ok: body.ok === true,
        service: typeof body.service === "string" ? body.service : "looper-gateway",
        version: typeof body.version === "string" ? body.version : null,
        mode: typeof body.mode === "string" ? body.mode : null,
      };
      return {
        ...status,
        artifact: {
          title: "LocalLoop gateway health",
          kind: "markdown",
          content: `**Status:** ${status.ok ? "healthy" : "unhealthy"}\n\n**Service:** ${markdownCell(status.service)}\n\n**Version:** ${markdownCell(status.version || "unknown")}\n\n**Mode:** ${markdownCell(status.mode || "unknown")}`,
        },
      };
    } catch {
      return { ok: false, error: "gateway_unreachable", message: "The LocalLoop gateway is offline or unreachable." };
    }
  }

  return { readPendingPins, health };
}

module.exports = {
  FIXED_SOURCE,
  FIXED_STATUS,
  PIN_FIELDS,
  buildPendingPinsUrl,
  createLocalLoopGatewayTools,
  sanitizePin,
  validatedBaseUrl,
};

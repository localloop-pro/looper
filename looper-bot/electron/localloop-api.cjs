"use strict";
const crypto = require("node:crypto");

function validatedBaseUrl(value) {
  const url = new URL(String(value || "").trim());
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || !["", "/"].includes(url.pathname)
      || (url.protocol !== "https:" && !(url.protocol === "http:" && loopback))) throw new Error("invalid base");
  return url.origin;
}
function markdownCell(value) {
  return String(value ?? "").replace(/[|\[\]`]/g, "\\$&").replace(/[\r\n]+/g, " ");
}
function safeHttpUrl(value) {
  try {
    const url = new URL(value);
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) return null;
    return url.href.replace(/\)/g, "%29");
  } catch { return null; }
}
function businessesTable(results) {
  const rows = results.map((r, i) => {
    const stars = r.avg_rating ? `⭐ ${markdownCell(r.avg_rating)}` : "no ratings yet";
    const dist = r.distance_km != null ? ` · ${markdownCell(r.distance_km)} km` : "";
    const card = safeHttpUrl(r.card_url);
    const website = safeHttpUrl(r.website);
    const link = card ? ` · [View card](${card})` : website ? ` · [Website](${website})` : "";
    return `| ${i + 1} | ${markdownCell(r.name)} | ${markdownCell(r.category)} | ${stars} · ${markdownCell(r.review_count || 0)} reviews${dist}${link} |`;
  });
  return ["| # | Business | Category | Community |", "|---|---|---|---|", ...rows].join("\n");
}

function createLocalLoopApi({ baseUrl, fetchImpl = globalThis.fetch, timeoutMs = 10000, log = console.log, now = () => performance.now() }) {
  let origin;
  try { origin = validatedBaseUrl(baseUrl); } catch {}
  async function request(path, params) {
    const operation = path === "/api/ingest/status" ? "bridgeStatus" : path.split("/").pop();
    const rid = (`lb-${crypto.randomUUID()}`).slice(0, 128);
    const started = now();
    let status = "invalid_api_base", cache = null, timer;
    const controller = new AbortController();
    try {
      if (!origin) return { ok: false, missingEnv: "LOOPER_API_BASE", error: "invalid_api_base", message: "LOOPER_API_BASE must be an HTTPS origin (HTTP is allowed only for loopback development)." };
      const url = new URL(path, origin);
      for (const [key, value] of Object.entries(params || {})) {
        if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
      }
      // Bound the entire response, including a stalled JSON body, even if abort is ignored.
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => reject({ name: "TimeoutError" }), timeoutMs);
      });
      const result = await Promise.race([(async () => {
        const response = await fetchImpl(url, { method: "GET", redirect: "error", headers: { Accept: "application/json", "X-Request-ID": rid }, signal: controller.signal });
        status = response.status;
        // Only known cache tokens may enter logs; an upstream header is untrusted.
        const header = response.headers?.get("x-looper-cache") ?? null;
        cache = header;
        if (!response.ok) return { ok: false, error: `looper_api_${status}`, message: `The LOOPER API answered ${status}.` };
        return { ok: true, data: await response.json() };
      })(), timeout]);
      return result.ok ? { ...result, timing: { ms: Math.max(0, now() - started), rid, cache } } : result;
    } catch (error) {
      const timedOut = error?.name === "TimeoutError";
      status = timedOut ? "timeout" : "unreachable";
      return { ok: false, error: timedOut ? "looper_api_timeout" : "looper_api_unreachable", message: timedOut ? "The LOOPER API did not answer within 10 seconds." : "The LOOPER API is offline. Is the backend running?" };
    } finally {
      clearTimeout(timer);
      controller.abort();
      const safeCache = ["HIT", "MISS", "BYPASS", "DISABLED"].includes(cache) ? cache : "-";
      try { log(`[looper-api] ${operation} ${Math.max(0, Math.round(now() - started))}ms status=${status} cache=${safeCache} rid=${rid}`); } catch {}
    }
  }
  async function localloopSearch(args = {}) {
    try {
      const reply = await request("/api/search", {
        q: String(args.query || ""),
        lat: args.lat,
        lng: args.lng,
        radius_km: args.radius_km,
        limit: Math.max(1, Math.min(20, Number(args.limit || 5))),
      });
      if (!reply.ok) return reply;
      const { data, timing } = reply;
      const results = Array.isArray(data.results) ? data.results : [];
      return {
        ok: true,
        timing,
        message: data.message,
        results,
        artifact: {
          title: `Local Loop: ${args.query}`,
          kind: "markdown",
          content: `${data.message || ""}\n\n${businessesTable(results)}\n\n_Ranked by community reviews, recency and distance only — never by payment._`,
        },
      };
    } catch (error) {
      return { ok: false, error: "looper_api_unreachable", message: "The LOOPER API is offline. Is the backend running?" };
    }
  }

  async function localloopDiscover(args = {}) {
    try {
      const reply = await request("/api/discover", {
        suburb: String(args.suburb || ""),
        category: args.category,
        radius_km: args.radius_km,
        limit: Math.max(1, Math.min(50, Number(args.limit || 10))),
        intent: "discover",
        session: "looper-desktop",
      });
      if (!reply.ok) return reply;
      const { data, timing } = reply;
      const results = Array.isArray(data.results) ? data.results : [];
      return {
        ok: true,
        timing,
        engine: data.engine,
        message: data.message,
        results,
        artifact: {
          title: `Local Loop: ${args.suburb}${args.category ? ` · ${args.category}` : ""}`,
          kind: "markdown",
          content: `${data.message || ""}\n\n${businessesTable(results)}\n\n_Engine: ${data.engine} · ranked by community reviews, recency and distance only._`,
        },
      };
    } catch (error) {
      return { ok: false, error: "looper_api_unreachable", message: "The LOOPER API is offline. Is the backend running?" };
    }
  }

  async function localloopBusinesses(args = {}) {
    try {
      const reply = await request("/api/businesses", {
        category: args.category,
        limit: Math.max(1, Math.min(50, Number(args.limit || 20))),
      });
      if (!reply.ok) return reply;
      const { data, timing } = reply;
      const results = Array.isArray(data.results) ? data.results : [];
      return {
        ok: true,
        timing,
        count: data.count,
        results,
        artifact: {
          title: `Local Loop businesses${args.category ? `: ${args.category}` : ""}`,
          kind: "markdown",
          content: businessesTable(results),
        },
      };
    } catch (error) {
      return { ok: false, error: "looper_api_unreachable", message: "The LOOPER API is offline. Is the backend running?" };
    }
  }

  async function localloopBridgeStatus() {
    try {
      const reply = await request("/api/ingest/status");
      if (!reply.ok) return reply;
      const { data, timing } = reply;
      const counts = data.counts || {};
      const recent = Array.isArray(data.recent_events) ? data.recent_events : [];
      const rows = recent.map((e) => `| ${e.received_at || ""} | ${e.event_type || ""} | ${e.status || ""} |`);
      const content = [
        `**Total events:** ${counts.total_events ?? 0} · **Active deals:** ${counts.active_deals ?? 0} · **Card businesses:** ${counts.card_businesses ?? 0}`,
        "",
        "| Received | Event | Status |",
        "|---|---|---|",
        ...rows,
      ].join("\n");
      return {
        ok: true,
        timing,
        counts,
        artifact: { title: "HybridCard bridge status", kind: "markdown", content },
      };
    } catch (error) {
      return { ok: false, error: "looper_api_unreachable", message: "The LOOPER API is offline. Is the backend running?" };
    }
  }


  return { search: localloopSearch, discover: localloopDiscover, businesses: localloopBusinesses, bridgeStatus: localloopBridgeStatus, businessesTable };
}
module.exports = { createLocalLoopApi };

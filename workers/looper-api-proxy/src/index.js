/**
 * Reverse-proxy Worker: api.localloop.ai → ORIGIN (Looper FastAPI).
 * Keeps public hostname stable while Coolify/Railway origin is being fixed.
 *
 * X-Request-ID (looper#17, docs/E6-RELEASE-GATE.md §1): a safe inbound id is
 * forwarded as is. A missing or unsafe one is replaced with the opaque cf-ray,
 * so Cloudflare logs and Looper trace records share one key. No PII is added.
 *
 * Origin key (looper#28): when the ORIGIN_KEY secret is set, every proxied
 * request carries it as x-looper-origin-key and any value the caller sent is
 * dropped first. The API rejects requests without it once LOOPER_ORIGIN_KEY is
 * set there, so the plain-HTTP origin can't be used to skip Cloudflare.
 * ORIGIN_KEY unset → requests are forwarded exactly as before.
 */

export const ORIGIN_KEY_HEADER = "x-looper-origin-key";

// Same rule as the Looper API: 8–128 chars of [A-Za-z0-9._:-], at least one
// letter (an all-digit id could be a phone number).
const REQUEST_ID_RE = /^[A-Za-z0-9._:-]{8,128}$/;

export function isSafeRequestId(value) {
  return typeof value === "string" && REQUEST_ID_RE.test(value) && /[A-Za-z]/.test(value);
}

export function ensureRequestId(headers) {
  const inbound = headers.get("x-request-id");
  if (isSafeRequestId(inbound)) return inbound;
  const ray = headers.get("cf-ray");
  const id = isSafeRequestId(ray) ? ray : crypto.randomUUID();
  headers.set("x-request-id", id);
  return id;
}

function jsonError(status, body, requestId) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "x-request-id": requestId },
  });
}

export default {
  async fetch(request, env) {
    const headers = new Headers(request.headers);
    const requestId = ensureRequestId(headers);
    const origin = (env.ORIGIN || "").replace(/\/$/, "");
    if (!origin) {
      return jsonError(500, { ok: false, error: "ORIGIN unset" }, requestId);
    }
    const incoming = new URL(request.url);
    const target = new URL(incoming.pathname + incoming.search, origin + "/");
    headers.delete("host");
    headers.set("x-forwarded-host", incoming.host);
    headers.set("x-forwarded-proto", incoming.protocol.replace(":", ""));
    if (env.ORIGIN_KEY) {
      headers.delete(ORIGIN_KEY_HEADER);
      headers.set(ORIGIN_KEY_HEADER, env.ORIGIN_KEY);
    }
    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
      // @ts-ignore
      init.duplex = "half";
    }
    try {
      return await fetch(target.toString(), init);
    } catch (err) {
      // The error text can name the origin URL: log it, never return it.
      console.error(JSON.stringify({ kind: "origin_unreachable", rid: requestId, error: String(err) }));
      return jsonError(502, { ok: false, error: "origin_unreachable" }, requestId);
    }
  },
};

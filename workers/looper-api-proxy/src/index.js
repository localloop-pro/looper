/**
 * Reverse-proxy Worker: api.localloop.ai → ORIGIN (Looper FastAPI).
 * Keeps public hostname stable while Coolify/Railway origin is being fixed.
 */
export default {
  async fetch(request, env) {
    const origin = (env.ORIGIN || "").replace(/\/$/, "");
    if (!origin) {
      return new Response(JSON.stringify({ ok: false, error: "ORIGIN unset" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      });
    }
    const incoming = new URL(request.url);
    const target = new URL(incoming.pathname + incoming.search, origin + "/");
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.set("x-forwarded-host", incoming.host);
    headers.set("x-forwarded-proto", incoming.protocol.replace(":", ""));
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
      return new Response(
        JSON.stringify({ ok: false, error: "origin_unreachable", detail: String(err) }),
        { status: 502, headers: { "content-type": "application/json" } }
      );
    }
  },
};

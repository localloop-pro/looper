import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const DEV_HOST = "127.0.0.1";
const DEV_PORT = 5173;

// index.html carries the production CSP. The dev server needs two extras:
// the React Fast Refresh inline preamble ('unsafe-inline' scripts) and the
// HMR WebSocket. They are added only while serving, never to `vite build`.
function devCspPlugin(): Plugin {
  return {
    name: "looper-dev-csp",
    apply: "serve",
    transformIndexHtml(html, ctx) {
      const address = ctx.server?.httpServer?.address();
      const port = address && typeof address === "object" ? address.port : DEV_PORT;
      const origin = `${DEV_HOST}:${port}`;
      return html
        .replace("script-src 'self';", "script-src 'self' 'unsafe-inline';")
        .replace("connect-src 'self'", `connect-src 'self' http://${origin} ws://${origin}`);
    },
  };
}

export default defineConfig({
  // Relative asset paths so the built dist/index.html loads over file://.
  base: "./",
  plugins: [react(), devCspPlugin()],
  server: {
    host: DEV_HOST,
    port: DEV_PORT,
  },
});

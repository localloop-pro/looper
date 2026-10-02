### looper-bot window hardening: sandbox, CSP, nav guard, IPC sender check (2026-10-02, looper#63)

- `looper-bot/electron/window-security.cjs` holds the rules as pure functions
  (tested in `electron/tests/window-security.test.cjs`); `main.cjs` only wires
  them in.
- Renderer is `sandbox: true` (plus contextIsolation, no nodeIntegration). The
  preload only uses `contextBridge` + `ipcRenderer`, so it runs sandboxed.
- `setWindowOpenHandler` always denies. A link opens in the system browser
  only if it is `https:` on `localloop.ai`, `localloop.pro` or `hybridcard.ai`
  (or a subdomain), with no userinfo. Web-search result links to other hosts
  are refused on purpose: the panel shows untrusted text. Main-process calls
  (`localloop_open_map`) still use their env-configured URL unchanged.
- `will-navigate` / `will-redirect` block anything but the dev server origin
  (dev) or the exact `dist/index.html` file URL (prod).
- Every `ipcMain.handle` calls `assertTrustedSender(event)` first: the sender
  must be the main window's top frame (matched by processId + routingId) at
  the app URL. A test fails if a new handler skips it.
- CSP lives in `index.html` as the production policy (no `unsafe-eval`, no
  inline scripts, connect-src only OpenAI). `vite.config.ts` adds the React
  Fast Refresh inline script and the HMR WebSocket during `vite serve` only.
- `vite.config.ts` gets `base: "./"`: with the default `/` the built
  `dist/index.html` asked for `file:///assets/...` and `npm start` could not
  load the bundle.

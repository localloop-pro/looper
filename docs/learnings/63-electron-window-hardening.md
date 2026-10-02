# looper#63 — Hardening the looper-bot Electron window

- Keep the security rules as pure functions (URL allowlist, navigation
  guard, IPC sender check) and wire them in `main.cjs`. Then `node --test`
  can prove them without launching Electron.
- A meta CSP has to fit both Vite dev and the `file://` build. Ship the strict
  policy in `index.html` and loosen it from a `transformIndexHtml` plugin with
  `apply: "serve"`. Vite dev needs an inline script (React refresh preamble)
  and the HMR `ws://` origin. It doesn't need `unsafe-eval`.
- Vite's default `base: "/"` breaks `loadFile`: the built HTML asks for
  `file:///assets/...`. Use `base: "./"` for Electron.
- To smoke-test without a key, write a throwaway Electron script in the
  scratchpad: stub `shell.openExternal`, `require` main.cjs, and call
  `executeJavaScript` to try eval, fetch, iframe, window.open and a
  navigation. Run it from a scratch cwd with `dist` symlinked so no
  `.env.local` or `data/` gets touched. macOS has no `timeout`, so wrap it
  with `perl -e 'alarm 45; exec @ARGV'`.

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const {
  EXTERNAL_HOST_ALLOWLIST,
  createAppTarget,
  decideWindowOpen,
  isAllowedExternalUrl,
  isTrustedIpcSender,
  shouldBlockNavigation,
} = require("../window-security.cjs");

const ROOT = path.join(__dirname, "..", "..");
const DIST_INDEX = path.join(ROOT, "dist", "index.html");
const DIST_URL = pathToFileURL(DIST_INDEX).href;
const devTarget = createAppTarget({ devUrl: "http://127.0.0.1:5173" });
const fileTarget = createAppTarget({ distIndexPath: DIST_INDEX });

test("allowlist is https-only LocalLoop and HybridCard hosts", () => {
  assert.deepEqual([...EXTERNAL_HOST_ALLOWLIST], ["localloop.ai", "localloop.pro", "hybridcard.ai"]);
  for (const ok of [
    "https://localloop.ai/?cat=Food",
    "https://www.localloop.ai/",
    "https://looper.localloop.ai/x",
    "https://hybridcard.ai/c/bondi-cafe",
    "https://LOCALLOOP.PRO/",
  ]) {
    assert.equal(isAllowedExternalUrl(ok), true, ok);
  }
});

test("openExternal refuses http:, file:, other schemes and unlisted hosts", () => {
  for (const bad of [
    "http://localloop.ai/",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "smb://evil.example/share",
    "https://evil.example/",
    "https://localloop.ai.evil.example/",
    "https://evillocalloop.ai/",
    "https://user:pw@localloop.ai/",
    "not a url",
    "",
    null,
  ]) {
    assert.equal(isAllowedExternalUrl(bad), false, String(bad));
  }
});

test("window.open is always denied; only allowlisted links go to the browser", () => {
  assert.deepEqual(decideWindowOpen("https://evil.example/"), { action: "deny", openExternal: null });
  assert.deepEqual(decideWindowOpen("http://localloop.ai/"), { action: "deny", openExternal: null });
  assert.deepEqual(decideWindowOpen("file:///etc/passwd"), { action: "deny", openExternal: null });
  assert.deepEqual(decideWindowOpen("https://localloop.ai/?q=cafe"), {
    action: "deny",
    openExternal: "https://localloop.ai/?q=cafe",
  });
});

test("navigation to https://evil.example is blocked in dev and prod", () => {
  for (const target of [devTarget, fileTarget]) {
    assert.equal(shouldBlockNavigation("https://evil.example", target), true);
    assert.equal(shouldBlockNavigation("https://localloop.ai/", target), true);
    assert.equal(shouldBlockNavigation("about:blank", target), true);
    assert.equal(shouldBlockNavigation("data:text/html,<h1>x</h1>", target), true);
  }
});

test("navigation stays allowed inside the app itself", () => {
  assert.equal(shouldBlockNavigation("http://127.0.0.1:5173/", devTarget), false);
  assert.equal(shouldBlockNavigation("http://127.0.0.1:5173/?reload=1#x", devTarget), false);
  assert.equal(shouldBlockNavigation("http://127.0.0.1:5174/", devTarget), true);
  assert.equal(shouldBlockNavigation("http://localhost:5173/", devTarget), true);

  assert.equal(shouldBlockNavigation(DIST_URL, fileTarget), false);
  assert.equal(shouldBlockNavigation(`${DIST_URL}#artifact`, fileTarget), false);
  assert.equal(shouldBlockNavigation("file:///etc/passwd", fileTarget), true);
  assert.equal(shouldBlockNavigation(pathToFileURL(path.join(ROOT, "dist", "other.html")).href, fileTarget), true);
  // Prod never trusts the dev server origin.
  assert.equal(shouldBlockNavigation("http://127.0.0.1:5173/", fileTarget), true);
});

test("a non-http dev server URL is refused at startup", () => {
  assert.throws(() => createAppTarget({ devUrl: "file:///tmp/x.html" }), /not an http/);
});

function frame(props) {
  return { processId: 4, routingId: 1, parent: null, url: "http://127.0.0.1:5173/", ...props };
}

test("IPC from the main window's top frame at the app URL is accepted", () => {
  const main = frame();
  assert.equal(isTrustedIpcSender(main, main, devTarget), true);
  // Different JS wrapper, same frame ids.
  assert.equal(isTrustedIpcSender(frame(), main, devTarget), true);
  const prodMain = frame({ url: DIST_URL });
  assert.equal(isTrustedIpcSender(prodMain, prodMain, fileTarget), true);
});

test("IPC from an unexpected frame is rejected", () => {
  const main = frame();
  // Missing sender (frame navigated away or destroyed) or no main window.
  assert.equal(isTrustedIpcSender(null, main, devTarget), false);
  assert.equal(isTrustedIpcSender(main, null, devTarget), false);
  // A subframe (iframe) in the same window.
  assert.equal(isTrustedIpcSender(frame({ routingId: 7, parent: main }), main, devTarget), false);
  // A different window / process.
  assert.equal(isTrustedIpcSender(frame({ processId: 9 }), main, devTarget), false);
  // The main frame after a foreign navigation slipped through.
  const hijacked = frame({ url: "https://evil.example/" });
  assert.equal(isTrustedIpcSender(hijacked, hijacked, devTarget), false);
  // Prod rejects the dev origin.
  assert.equal(isTrustedIpcSender(main, main, fileTarget), false);
});

test("main.cjs sandboxes the window and guards navigation and every IPC handler", () => {
  const main = fs.readFileSync(path.join(__dirname, "..", "main.cjs"), "utf8");
  assert.match(main, /contextIsolation: true/);
  assert.match(main, /nodeIntegration: false/);
  assert.match(main, /sandbox: true/);
  assert.match(main, /setWindowOpenHandler\(/);
  assert.match(main, /on\("will-navigate", blockForeignNavigation\)/);
  assert.match(main, /on\("will-redirect", blockForeignNavigation\)/);

  const handlers = [...main.matchAll(/ipcMain\.handle\("([^"]+)",[^\n]*\n\s*assertTrustedSender\(event\);/g)].map((m) => m[1]);
  const all = [...main.matchAll(/ipcMain\.handle\("([^"]+)"/g)].map((m) => m[1]);
  assert.ok(all.length >= 3);
  assert.deepEqual(handlers.sort(), all.sort(), "every ipcMain.handle must call assertTrustedSender first");
});

test("preload only uses contextBridge and ipcRenderer (works sandboxed)", () => {
  const preload = fs.readFileSync(path.join(__dirname, "..", "preload.cjs"), "utf8");
  const requires = [...preload.matchAll(/require\("([^"]+)"\)/g)].map((m) => m[1]);
  assert.deepEqual(requires, ["electron"]);
  assert.match(preload, /const \{ contextBridge, ipcRenderer \} = require\("electron"\)/);
});

function cspOf(html) {
  const match = html.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/);
  assert.ok(match, "CSP meta tag present");
  return Object.fromEntries(
    match[1].split(";").map((part) => {
      const [name, ...values] = part.trim().split(/\s+/);
      return [name, values];
    }),
  );
}

function assertProductionCsp(html) {
  const csp = cspOf(html);
  assert.deepEqual(csp["default-src"], ["'self'"]);
  assert.deepEqual(csp["script-src"], ["'self'"]);
  assert.ok(!Object.values(csp).flat().includes("'unsafe-eval'"), "no unsafe-eval in production");
  assert.deepEqual(csp["connect-src"], ["'self'", "https://api.openai.com", "wss://api.openai.com"]);
  assert.deepEqual(csp["object-src"], ["'none'"]);
  assert.deepEqual(csp["frame-src"], ["'none'"]);
  assert.deepEqual(csp["base-uri"], ["'none'"]);
}

test("index.html ships a strict production CSP", () => {
  assertProductionCsp(fs.readFileSync(path.join(ROOT, "index.html"), "utf8"));
});

test("built dist/index.html keeps the production CSP and relative assets", { skip: !fs.existsSync(DIST_INDEX) && "run npm run build first" }, () => {
  const html = fs.readFileSync(DIST_INDEX, "utf8");
  assertProductionCsp(html);
  assert.ok(!/(src|href)="\/assets\//.test(html), "assets must be relative so file:// loads them");
});

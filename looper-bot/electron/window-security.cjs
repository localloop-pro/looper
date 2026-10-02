"use strict";

// Window hardening for the Looper Electron app (looper#63).
// Pure functions only, so electron/tests can check them without launching
// Electron. main.cjs wires them into the BrowserWindow and ipcMain handlers.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

// Hosts the renderer may hand to shell.openExternal (exact host or any
// subdomain). https only. Web-search links to other hosts are refused on
// purpose: the renderer shows untrusted text, so a link must not become a
// way to open arbitrary sites or protocol handlers on Bill's machine.
const EXTERNAL_HOST_ALLOWLIST = Object.freeze(["localloop.ai", "localloop.pro", "hybridcard.ai"]);

function parseUrl(value) {
  try {
    return new URL(String(value));
  } catch {
    return null;
  }
}

function hostMatches(hostname, allowedHost) {
  const host = String(hostname || "").toLowerCase().replace(/\.$/, "");
  return host === allowedHost || host.endsWith(`.${allowedHost}`);
}

function isAllowedExternalUrl(value, allowlist = EXTERNAL_HOST_ALLOWLIST) {
  const url = parseUrl(value);
  if (!url || url.protocol !== "https:") return false;
  if (url.username || url.password) return false;
  return allowlist.some((allowed) => hostMatches(url.hostname, allowed));
}

// What the window is allowed to show: the Vite dev server origin (dev) or the
// built dist/index.html (prod). Nothing else.
function createAppTarget({ devUrl, distIndexPath }) {
  if (devUrl) {
    const url = parseUrl(devUrl);
    if (!url || (url.protocol !== "http:" && url.protocol !== "https:")) {
      throw new Error(`VITE_DEV_SERVER_URL is not an http(s) URL: ${devUrl}`);
    }
    return { kind: "dev", origin: url.origin };
  }
  return { kind: "file", href: pathToFileURL(path.resolve(distIndexPath)).href };
}

function isAppUrl(value, target) {
  const url = parseUrl(value);
  if (!url || !target) return false;
  if (target.kind === "dev") return url.origin === target.origin;
  if (url.protocol !== "file:") return false;
  url.hash = "";
  url.search = "";
  return url.href === target.href;
}

// will-navigate / will-redirect: true means "block it".
function shouldBlockNavigation(value, target) {
  return !isAppUrl(value, target);
}

// setWindowOpenHandler: always deny a new window. An allowlisted https link
// is handed to the system browser instead.
function decideWindowOpen(value, allowlist = EXTERNAL_HOST_ALLOWLIST) {
  return {
    action: "deny",
    openExternal: isAllowedExternalUrl(value, allowlist) ? String(value) : null,
  };
}

// Every ipcMain.handle calls this first. Accept only the main window's top
// frame while it shows the app itself.
function isTrustedIpcSender(senderFrame, mainFrame, target) {
  if (!senderFrame || !mainFrame) return false;
  // WebFrameMain objects are matched by process + routing id, not identity.
  const sameFrame =
    senderFrame === mainFrame ||
    (Number.isInteger(senderFrame.processId) &&
      senderFrame.processId === mainFrame.processId &&
      senderFrame.routingId === mainFrame.routingId);
  if (!sameFrame) return false;
  if (senderFrame.parent) return false;
  return isAppUrl(senderFrame.url, target);
}

module.exports = {
  EXTERNAL_HOST_ALLOWLIST,
  createAppTarget,
  decideWindowOpen,
  isAllowedExternalUrl,
  isAppUrl,
  isTrustedIpcSender,
  shouldBlockNavigation,
};

"use strict";

// Prompt-injection guard for tools that act on the owner's computer (looper#64).
//
// The voice model reads untrusted text (web_search results, gateway pins,
// records). A crafted page could tell it to type, click or delete, so these
// tools need a human "Allow once" in a native dialog before they run.
// Everything here is pure except confirmToolCall, which takes the Electron
// dialog function as a parameter so it can be tested without Electron.

// Tools that touch the desktop, the screen or delete local data.
const CONFIRM_TOOLS = Object.freeze([
  "computer_open_app",
  "computer_type_text",
  "computer_press_key",
  "computer_click",
  "computer_scroll",
  "screen_snapshot",
  "ui_inspect",
  "records_delete",
]);

// Every other tool the dispatcher in main.cjs knows. They run without a dialog.
const ALLOWED_TOOLS = Object.freeze([
  "set_mode",
  "artifact_show",
  "show_menu",
  "web_search",
  "localloop_search",
  "localloop_discover",
  "localloop_businesses",
  "localloop_open_map",
  "localloop_bridge_status",
  "localloop_pending_pins",
  "localloop_gateway_health",
  "image_generate",
  "thumbnail_loading_prepare",
  "thumbnail_reference_add",
  "thumbnail_generate",
  "thumbnail_edit",
  "thumbnail_select",
  "thumbnail_grid",
  "mermaid_render",
  "note_add",
  "records_create",
  "records_search",
  "records_update",
]);

const CONFIRM_SET = new Set(CONFIRM_TOOLS);
const ALLOWED_SET = new Set(ALLOWED_TOOLS);

const SUMMARY_MAX_CHARS = 200;
const DENIED_RESULT = Object.freeze({
  ok: false,
  error: "denied_by_user",
  message: "Bill declined this action in the confirmation dialog. Nothing was done. Tell him it was declined.",
});

/** "confirm" | "allow" | "unknown" */
function classifyTool(name) {
  if (typeof name !== "string") return "unknown";
  if (CONFIRM_SET.has(name)) return "confirm";
  if (ALLOWED_SET.has(name)) return "allow";
  return "unknown";
}

function needsConfirmation(name) {
  return classifyTool(name) === "confirm";
}

/** On unless the variable is exactly "off". */
function confirmationEnabled(env = process.env) {
  return env.LOOPER_CONFIRM_RISKY_TOOLS !== "off";
}

// Make untrusted text safe to show: control/format characters (newlines,
// tabs, ANSI escapes, bidi overrides, zero-width chars) become visible
// escapes, then the result is cut to max code points.
function escapeForDialog(value, max = SUMMARY_MAX_CHARS) {
  const text = String(value ?? "");
  const escaped = text.replace(/[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/gu, (ch) => {
    if (ch === "\n") return "\\n";
    if (ch === "\r") return "\\r";
    if (ch === "\t") return "\\t";
    return `\\u${ch.codePointAt(0).toString(16).padStart(4, "0")}`;
  });
  const chars = Array.from(escaped);
  if (chars.length <= max) return escaped;
  return `${chars.slice(0, max).join("")}… (${chars.length} chars total)`;
}

function summarizeToolCall(name, args) {
  const a = args && typeof args === "object" ? args : {};
  const s = (v) => escapeForDialog(v);
  switch (name) {
    case "computer_type_text":
      return `Type this text into the active app:\n"${s(a.text)}"`;
    case "computer_open_app":
      return `Open the app: ${s(a.appName)}`;
    case "computer_press_key":
      return `Press the key: ${s(a.key)} (x${s(a.repeat ?? 1)})`;
    case "computer_click":
      return `Click the screen at x=${s(a.x)}, y=${s(a.y)}`;
    case "computer_scroll":
      return `Scroll ${s(a.direction ?? "down")} (${s(a.amount ?? 4)} steps)`;
    case "screen_snapshot":
      return "Take a screenshot of your whole screen.";
    case "ui_inspect":
      return "Read the name and window of the app in front.";
    case "records_delete":
      return `Delete the record with id: ${s(a.id)}`;
    default:
      return `Run ${s(name)}`;
  }
}

function buildDialogOptions(name, args) {
  return {
    type: "warning",
    title: "Looper wants to act on your computer",
    message: `Allow Looper to run ${escapeForDialog(name, 60)}?`,
    detail: `${summarizeToolCall(name, args)}\n\nOnly allow this if you asked Looper to do it.`,
    buttons: ["Allow once", "Deny"],
    defaultId: 1,
    cancelId: 1,
    noLink: true,
  };
}

// One dialog at a time, so a burst of tool calls cannot stack prompts.
let dialogQueue = Promise.resolve();

/**
 * Ask the owner. Resolves true only on an explicit "Allow once" click; Deny,
 * Esc, a closed dialog or any error resolves false (fail closed).
 */
function confirmToolCall({ name, args, showMessageBox, parentWindow }) {
  const options = buildDialogOptions(name, args);
  const ask = async () => {
    try {
      const result = parentWindow && !parentWindow.isDestroyed?.()
        ? await showMessageBox(parentWindow, options)
        : await showMessageBox(options);
      return result?.response === 0;
    } catch {
      return false;
    }
  };
  const run = dialogQueue.then(ask, ask);
  dialogQueue = run.catch(() => false);
  return run;
}

module.exports = {
  ALLOWED_TOOLS,
  CONFIRM_TOOLS,
  DENIED_RESULT,
  SUMMARY_MAX_CHARS,
  buildDialogOptions,
  classifyTool,
  confirmToolCall,
  confirmationEnabled,
  escapeForDialog,
  needsConfirmation,
  summarizeToolCall,
};

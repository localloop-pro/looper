### looper-bot: native Allow/Deny before computer-control and delete tools (2026-10-02, looper#64)

- `looper-bot/electron/tool-policy.cjs` lists every tool the dispatcher knows.
  `computer_*`, `screen_snapshot`, `ui_inspect` and `records_delete` need a
  human click on **Allow once** in `dialog.showMessageBox` from Electron main;
  read-only LocalLoop tools, `web_search`, artifacts and Mermaid do not. Unknown
  names are rejected before anything else runs. A test fails if the policy and
  the `if (name === ...)` branches in `main.cjs` ever drift apart.
- The gate sits in `ipcMain.handle("tools:execute")`, not in `createWindow`,
  so the window-hardening work can land independently.
- Deny is the default and the Esc button; errors fail closed. Deny returns
  `{ ok: false, error: "denied_by_user" }` so the voice session keeps going.
- This replaces the old "typing and Enter need no extra approval" rule: the
  thing being protected against is the model itself following injected text,
  so the model's own `confirmed: true` is not enough.
- `LOOPER_CONFIRM_RISKY_TOOLS=off` (exact string only) disables it and logs a
  warning at startup. Default on.

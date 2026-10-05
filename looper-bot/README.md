# Looper Bot

Looper Bot is a local Electron desktop AI companion with realtime voice, a visual artifact panel, image generation, web search, notes, and opt-in macOS computer control.

It is built with Electron, React, Vite, TypeScript, and the OpenAI Realtime API.

## Features

- Realtime speech-to-speech conversation with OpenAI Realtime.
- Animated companion face with listening, thinking, speaking, and working states.
- Artifact panel for markdown, menus, notes, Mermaid diagrams, generated images, records, and progress.
- YouTube thumbnail board with persistent numbered generations and image edits.
- Optional Exa-powered web search.
- Local notes and records stored at runtime under `data/`.
- Optional computer-use mode for opening apps, clicking, typing, scrolling, screenshots, and UI inspection on macOS.

## Requirements

- macOS
- Node.js 20+
- npm
- An OpenAI API key with Realtime and image generation access
- Optional: an Exa API key for web search

## Quick Start

```bash
git clone https://github.com/rileybrown/looper-bot.git
cd looper-bot
npm install
cp .env.example .env.local
npm run dev
```

Edit `.env.local` before starting voice features:

```bash
OPENAI_API_KEY=your_openai_api_key_here
EXA_API_KEY=your_exa_api_key_here
# F4.3 read-only pending-pin cockpit (activate only after the gateway route is live)
LOCALLOOP_GATEWAY_URL=https://looper.localloop.ai
LOOPER_BOT_READ_TOKEN=<same-random-32+-byte-secret-as-the-LocalLoop-Worker>
```

`OPENAI_API_KEY` is required. `EXA_API_KEY` is optional; web search will show a setup message when it is missing.
`LOOPER_BOT_READ_TOKEN` is optional unless using the pending-pin cockpit. Keep
it only in Electron's `.env.local` and the LocalLoop Worker secret store; never
put it in browser configuration. Looper reads the moderation queue only through
the audited Bot Gateway endpoint and never queries Supabase directly.

## macOS Permissions

Looper Bot runs locally. Depending on the features you use, macOS may ask for:

- Microphone permission for voice conversation.
- Accessibility permission for computer-control tools.
- Screen Recording permission for screenshots and screen inspection.

Computer-control tools are blocked until the app is in computer-use mode.

### Confirmation dialog for risky tools (looper#64)

Looper reads untrusted text (web search results, map pins, records). A crafted
page could try to tell it to type, click or delete. So these tools always show
a native **Allow once / Deny** dialog before they run:

`computer_open_app`, `computer_type_text`, `computer_press_key`,
`computer_click`, `computer_scroll`, `screen_snapshot`, `ui_inspect`,
`records_delete`.

The dialog names the tool and shows a short summary of what it will do (for
typing, the text itself; a new line shows as `\n`). **Deny** is the default
button, so Enter or Esc denies. On Deny nothing runs, the tool returns
`{ ok: false, error: "denied_by_user" }` and Looper says it was declined. Read-only
tools (LocalLoop search, web search, artifacts, Mermaid) never ask.

To turn the dialog off, put this in `.env.local` and restart Looper:

```bash
LOOPER_CONFIRM_RISKY_TOOLS=off
```

Only the exact value `off` works. On startup the terminal then prints:

```text
[tool-policy] LOOPER_CONFIRM_RISKY_TOOLS=off: computer-control and delete tools run WITHOUT a confirmation dialog.
```

Delete the line (or set it to anything else) to turn the dialog back on.

## Development

```bash
npm run dev
```

This starts Vite on `127.0.0.1:5173` and launches Electron.

Other useful commands:

```bash
npm run typecheck
npm run build
npm test
npm start
```

## Runtime Data

The app creates a local `data/` directory for notes, records, generated images, and thumbnail-board state. That directory is intentionally ignored by Git.

Do not commit:

- `.env.local`
- Anything under `data/`
- `dist/`
- `node_modules/`

## Security Notes

- API keys are loaded only from local environment files.
- The LocalLoop gateway bearer token stays in the Electron main process and is
  never exposed through the preload bridge or renderer.
- `.env.local` and all `.env.*` files are ignored except `.env.example`.
- Generated images and local database files are ignored.
- Computer-control, screenshot, UI-inspect and record-delete tools need a click
  on **Allow once** in a native dialog (see above), including typing and
  pressing Enter. The policy lives in `electron/tool-policy.cjs`.

Before publishing a fork, run:

```bash
npm run typecheck
npm run build
git status --short
```

Then verify that no local secrets or runtime data are staged.

## License

MIT

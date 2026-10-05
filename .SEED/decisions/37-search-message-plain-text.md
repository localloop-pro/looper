# `/api/search` `message` stays plain text; renderers escape (2026-10-02, looper#37)

- `message` echoes the caller's `q` verbatim and is returned as JSON text. The
  API does **not** HTML-escape it: Jarvis (`escapeHtml`), the widget
  (`textContent`) and the voice output all treat it as text, so escaping
  here would show or speak `&amp;`.
- The legacy map panel puts it into `innerHTML` raw in two copies:
  localloop.pro-main `index.html` (tracked by MAP#324) and
  `assets/js/main-map.js` (tracked by MAP#332, since #324 is limited
  to the `index.html` panel). Both fixes belong in localloop.pro-main.
- `tests/test_search_message_plain_text.py` pins the echo on both the
  results and no-results paths, and fails if anyone adds escaping here.

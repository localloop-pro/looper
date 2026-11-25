# tools/callgraph — intent prompt + call graph generator

Writes `plans/INTENT_PROMPT_CALL_GRAPH.md` locally (gitignored): the hand-written
intent prompt (`intent.md`) plus a generated, complete function-level call graph of
the non-test code. Regenerate: `python3 tools/callgraph/build.py`.

```bash
python3 tools/callgraph/build.py
```

- `pycg.py` — Python extractor (stdlib `ast` only): backend, brain, tools, scripts, training.
- `jscg.js` — JS/TS extractor using the TypeScript parser. `build.py` takes it from
  `looper-bot/node_modules` if present; otherwise it downloads the version pinned in
  `looper-bot/package-lock.json` once into `~/.cache/looper-callgraph`, outside the repo.
- `render.py` — merges `intent.md` with the generated sections at the `<!-- GRAPH -->` marker.
- Edit `intent.md` to change the prose; never edit the generated file by hand.

Static analysis only: nothing from the analysed code is imported or executed.

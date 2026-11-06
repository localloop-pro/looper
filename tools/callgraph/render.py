#!/usr/bin/env python3
"""render.py ROOT py.json js.json intent.md OUT.md SHA DATE
Merges the hand-written intent prompt with generated call-graph sections at the <!-- GRAPH --> marker."""
import json, os, re, sys
from collections import defaultdict, OrderedDict

ROOT, PYJ, JSJ, INTENT, OUT, SHA, DATE = sys.argv[1:8]
py = json.load(open(PYJ))["modules"]
js = json.load(open(JSJ))["modules"]
MAX_EXT = 25

SUBSYSTEMS = OrderedDict([
    ("backend", ("Backend API (FastAPI + SQLite)", lambda k: k.startswith("backend"), "py")),
    ("brain", ("TypeDB brain sync (additive knowledge graph)", lambda k: k.startswith("brain"), "py")),
    ("tools", ("Owner tools, scripts, training export", lambda k: k.startswith(("tools", "scripts", "training")), "py")),
    ("web", ("Browser widget + Jarvis voice scripts (vanilla JS, served under /web)", lambda k: k.startswith("web/"), "js")),
    ("workers", ("Cloudflare Worker edge proxy (api.localloop.ai)", lambda k: k.startswith("workers/"), "js")),
    ("electron", ("Looper desktop bot: Electron main process (tool dispatcher)", lambda k: k.startswith("looper-bot/electron"), "js")),
    ("renderer", ("Looper desktop bot: React renderer (OpenAI Realtime over WebRTC)", lambda k: k.startswith("looper-bot/src"), "js")),
])

def mods_for(key):
    _, pred, lang = SUBSYSTEMS[key]
    src = py if lang == "py" else js
    return OrderedDict((k, v) for k, v in src.items() if pred(k)), lang

def short(target, cur_mod):
    m, _, q = target.partition(":")
    return f"`{q}`" if m == cur_mod else f"`{m}:{q}`"

def mid(s):
    return "m_" + re.sub(r"[^A-Za-z0-9_]", "_", s)

def fn_sort(items):
    return sorted(items, key=lambda kv: (kv[0] == "<module>", kv[1].get("line", 0)))

out = []
w = out.append

# ---------- §2 system map
w("## 2. System map (generated)\n")
w("| Subsystem | Files | Functions | Lines | Role |")
w("|---|---:|---:|---:|---|")
for key, (title, pred, lang) in SUBSYSTEMS.items():
    ms, _ = mods_for(key)
    nf = sum(len(v["functions"]) - 1 for v in ms.values())
    nl = sum(v.get("lines", 0) for v in ms.values())
    w(f"| `{key}` | {len(ms)} | {nf} | {nl} | {title} |")
w("")
w("Tests are excluded from the graphs below; see §7 for the inventory.\n")

# ---------- §3 entry points
w("## 3. Entry points (generated)\n")
w("### 3.1 HTTP routes (backend)\n")
w("| Route | Handler | Direct internal callees |")
w("|---|---|---|")
routes = []
for m, info in py.items():
    for q, f in info["functions"].items():
        if f.get("route"):
            routes.append((f["route"], m, q, f))
def full_route(route, m):
    verb, _, path = route.partition(" ")
    return f"{verb} {py[m].get('route_prefix', '')}{path}"
for route, m, q, f in sorted(routes, key=lambda r: (full_route(r[0], r[1]).split(" ", 1)[1], r[0])):
    callees = ", ".join(short(t, m) for t in f["calls"]) or "—"
    w(f"| `{full_route(route, m)}` | `{m}:{q}` (L{f['line']}) | {callees} |")
w("")
main_mod = py.get("backend.main", {})
inc = main_mod.get("functions", {}).get("<module>", {}).get("includes", [])
if inc:
    w("Router registration order in `backend/main.py`: " + " → ".join(f"`{i['router']}`" for i in inc) + ".\n")
mw = [e for e in main_mod.get("functions", {}).get("<module>", {}).get("external", []) if "add_middleware" in e or "mount" in e]
w("Middleware, in the order a request passes through it (Starlette runs the last-added middleware first): `CorrelationMiddleware` → `CORSMiddleware` → `OriginKeyGuard` → `PublicReadBoundary` → route. The static `/web` mount serves the widget and Jarvis scripts.\n")

# tools allowlist from tool-policy.cjs
pol_path = os.path.join(ROOT, "looper-bot/electron/tool-policy.cjs")
w("### 3.2 Desktop bot tools (from `looper-bot/electron/tool-policy.cjs`)\n")
if os.path.exists(pol_path):
    src = open(pol_path, encoding="utf-8").read()
    def arr(name):
        mt = re.search(name + r"\s*=\s*Object\.freeze\(\[(.*?)\]\)", src, re.S)
        return re.findall(r"\"([a-z_]+)\"", mt.group(1)) if mt else []
    confirm, allowed = arr("CONFIRM_TOOLS"), arr("ALLOWED_TOOLS")
    w(f"- **Run without a dialog ({len(allowed)}):** " + ", ".join(f"`{t}`" for t in allowed))
    w(f"- **Require a confirmation dialog ({len(confirm)}):** " + ", ".join(f"`{t}`" for t in confirm))
    w("- Dispatch: renderer `LooperRealtimeClient.executeFunctionCalls` → preload `window.looper.executeTool` → IPC `tools:execute` → `main.cjs` handler → `tool-policy.classifyTool/confirmToolCall` → per-tool function (see §5 electron).\n")

# IPC / event channels
w("### 3.3 IPC, bus and DOM event channels (generated from call sites)\n")
js_defs = {f"{m}:{q}" for m, info in js.items() for q in info["functions"]}
CH_RE = re.compile(r'^(?:new )?([A-Za-z_$][\w$.]*?)\.?(handle|handleOnce|on|once|off|emit|invoke|send|addEventListener|removeEventListener|dispatchEvent|exposeInMainWorld|postMessage|CustomEvent|subscribe|publish)\("([^"]+)"\)$')
chan = defaultdict(lambda: defaultdict(list))
for m, info in js.items():
    for q, f in info["functions"].items():
        for e in f["external"]:
            mt = CH_RE.match(e)
            if not mt:
                continue
            recv, verb, name = mt.groups()
            if verb in ("addEventListener", "removeEventListener") and name in ("click", "keydown", "keyup", "input", "change", "submit", "resize", "scroll", "load", "DOMContentLoaded", "mousedown", "mouseup", "touchstart", "touchend", "focus", "blur", "ended", "error", "pointerdown", "pointerup", "mousemove", "visibilitychange", "beforeunload", "message"):
                continue
            handler = f"{m}:{recv}.{verb}(\"{name}\")"
            chan[name][verb].append(handler if handler in js_defs else f"{m}:{q}")
if chan:
    w("| Channel / event | Producers (emit, invoke, send, dispatch) | Consumers (handle, on, addEventListener) |")
    w("|---|---|---|")
    for name in sorted(chan):
        prod = sorted({s for v, ss in chan[name].items() if v in ("emit", "invoke", "send", "dispatchEvent", "postMessage", "publish", "CustomEvent") for s in ss})
        cons = sorted({s for v, ss in chan[name].items() if v in ("handle", "handleOnce", "on", "once", "addEventListener", "subscribe") for s in ss})
        if not prod and not cons:
            continue
        w(f"| `{name}` | {', '.join(f'`{p}`' for p in prod) or '—'} | {', '.join(f'`{c}`' for c in cons) or '—'} |")
    w("")

# ---------- §4 module graphs
w("## 4. Module-level call graphs (generated, Mermaid)\n")
w("Edge labels are the number of distinct function-level call/reference edges between the two modules.\n")
for key, (title, pred, lang) in SUBSYSTEMS.items():
    ms, _ = mods_for(key)
    edges = defaultdict(int)
    for m, info in ms.items():
        for q, f in info["functions"].items():
            for t in f["calls"] + f["refs"] + f.get("jsx", []) + f.get("uses", []) + f.get("probable", []):
                tm = t.partition(":")[0]
                if tm != m:
                    edges[(m, tm)] += 1
    w(f"### 4.{list(SUBSYSTEMS).index(key)+1} {title}\n")
    w("```mermaid")
    w("flowchart LR")
    nodes = {m for m, info in ms.items() if len(info["functions"]) > 1 or any(info["functions"]["<module>"].get(k) for k in ("calls", "refs", "external"))}
    for a, b in edges:
        nodes.add(a); nodes.add(b)
    for n in sorted(nodes):
        label = n if n in ms else n + " (other subsystem)"
        w(f'  {mid(n)}["{label}"]')
    if not edges:
        w("  %% no cross-module calls inside this subsystem")
    for (a, b), c in sorted(edges.items()):
        w(f"  {mid(a)} -->|{c}| {mid(b)}")
    w("```\n")

# ---------- §5 function-level
w("## 5. Function-level call graph (generated, complete for non-test code)\n")
w("Legend: `→ calls` internal functions called; `→ calls?` probable call resolved by a unique method name across the subsystem (dynamic receiver); "
  "`→ refs` internal functions passed as values (callbacks, handlers, registries, middleware); `→ uses` internal module attributes or ORM columns touched; "
  f"`→ ext` external/library calls (deduplicated, first {MAX_EXT} shown); `← by` internal callers. `<module>` is top-level code that runs on import/load. "
  "A node like `handler [name == \"x\"]` is the branch of that handler taken for that literal (tool dispatch, switch/case). L = line number.\n")
for key, (title, pred, lang) in SUBSYSTEMS.items():
    ms, _ = mods_for(key)
    w(f"### 5.{list(SUBSYSTEMS).index(key)+1} {title}\n")
    for m, info in ms.items():
        path = info["path"]
        hdr = f"#### `{m}` — [{path}]({path})"
        w(hdr + "\n")
        meta = []
        if info.get("doc"):
            meta.append(f"Purpose: {info['doc']}")
        if info.get("env"):
            meta.append("Env: " + ", ".join(f"`{e}`" for e in info["env"]))
        if info.get("globals"):
            meta.append("Browser/UMD globals exposed: " + ", ".join(f"`{g}`" + (f" = `{v}`" if v else "") for g, v in info["globals"].items()))
        if info.get("aliases"):
            meta.append("Global aliases used: " + ", ".join(f"`{a}` → `{v}`" for a, v in info["aliases"].items()))
        if info.get("exports"):
            meta.append("Exports: " + ", ".join(f"`{e}`" for e in info["exports"]))
        if info.get("classes"):
            meta.append("Classes: " + ", ".join(f"`{c}`" + (f" ({', '.join(v['bases'])})" if v["bases"] else "") for c, v in info["classes"].items()))
        for x in meta:
            w(f"- {x}")
        if meta:
            w("")
        for q, f in fn_sort(info["functions"].items()):
            if q == "<module>" and not (f["calls"] or f["refs"] or f["external"] or f.get("jsx")):
                continue
            tags = []
            if f.get("async"):
                tags.append("async")
            if f.get("route"):
                tags.append(f"**{full_route(f['route'], m)}**")
            if f.get("exported"):
                tags.append("exported")
            if f.get("kind") == "class":
                tags.append("class" + (f" {f.get('extends')}" if f.get("extends") else ""))
            if f.get("kind") == "branch":
                tags.append("branch")
            decos = [d for d in f.get("decorators", []) if not f.get("route") or not d.startswith(("router.", "app."))]
            if decos:
                tags.append("@" + ", @".join(decos))
            args = f.get("args") or f.get("params") or []
            sig = f"`{q}`" if f.get("kind") in ("branch", "class") else (f"`{q}({', '.join(args)})`" if q != "<module>" else "`<module>` (top-level code)")
            line = f"- {sig} L{f['line']}" + (" · " + " · ".join(tags) if tags else "")
            w(line)
            callees = f["calls"] + f.get("jsx", [])
            if callees:
                w("  - → calls: " + ", ".join(short(t, m) for t in callees))
            if f.get("includes"):
                w("  - → includes routers: " + ", ".join(f"`{i['router']}`" + (f" (prefix `{i['prefix']}`)" if i.get("prefix") else "") for i in f["includes"]))
            if f.get("probable"):
                w("  - → calls?: " + ", ".join(short(t, m) for t in f["probable"]))
            if f["refs"]:
                w("  - → refs: " + ", ".join(short(t, m) for t in f["refs"]))
            if f.get("uses"):
                w("  - → uses: " + ", ".join(short(t, m) for t in f["uses"]))
            if f["external"]:
                ext = f["external"][:MAX_EXT]
                more = len(f["external"]) - len(ext)
                w("  - → ext: " + ", ".join(f"`{e}`" for e in ext) + (f" … +{more} more" if more > 0 else ""))
            if f["called_by"]:
                w("  - ← by: " + ", ".join(short(t, m) for t in f["called_by"]))
            elif q != "<module>":
                w("  - ← by: (none internal: entry point, handler, exported API, or dead code)")
        w("")

# ---------- §7 config surface
w("## 6. Configuration surface (generated)\n")
env = defaultdict(set)
for m, info in list(py.items()) + list(js.items()):
    for e in info.get("env", []):
        env[e].add(m)
w("| Env var | Read by |")
w("|---|---|")
for e in sorted(env):
    w(f"| `{e}` | {', '.join(f'`{m}`' for m in sorted(env[e]))} |")
w("")

# ---------- §8 tests inventory
w("## 7. Test inventory (generated)\n")
tests = []
for base in ("backend/tests", "web/tests", "workers/looper-api-proxy/test", "looper-bot/electron/tests", "looper-bot/src"):
    p = os.path.join(ROOT, base)
    if not os.path.isdir(p):
        continue
    for dp, dns, fns in os.walk(p):
        dns[:] = [d for d in dns if d not in ("node_modules", "__pycache__")]
        for fn in sorted(fns):
            if re.search(r"(^test_.*\.py$|\.test\.(js|mjs|cjs|ts|tsx)$|\.playwright\.js$|^conftest\.py$)", fn):
                tests.append(os.path.relpath(os.path.join(dp, fn), ROOT))
by_dir = defaultdict(list)
for t in tests:
    by_dir[os.path.dirname(t)].append(os.path.basename(t))
for d in sorted(by_dir):
    w(f"- `{d}/` ({len(by_dir[d])}): " + ", ".join(f"`{x}`" for x in by_dir[d]))
w("")

generated = "\n".join(out)
intent = open(INTENT, encoding="utf-8").read()
doc = intent.replace("{{SHA}}", SHA).replace("{{DATE}}", DATE).replace("<!-- GRAPH -->", generated)
open(OUT, "w", encoding="utf-8").write(doc)
print(f"wrote {OUT}: {doc.count(chr(10))} lines, {len(doc)} bytes")
